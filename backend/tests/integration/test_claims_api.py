import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.use_cases import record_run
from delta_feed.content.models import Article
from delta_feed.knowledge.models import Claim, Entity

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_client():
    user = get_user_model().objects.create_user(username="claims-owner", password="password")
    client = Client()
    client.force_login(user)
    return client


def make_context():
    entity = Entity.objects.create(name="Widget", type="software")
    article = Article.objects.create(
        url="https://example.org/widget", title="Widget release", body="Widget supports ARM."
    )
    run = record_run(
        source_article=article,
        status=AnalysisRun.Status.COMPLETED,
        model_version="test-model",
        prompt_version="test-prompt",
    )
    return entity, article, run


def payload(entity, run, text):
    quote = "Widget supports ARM."
    return {
        "entity_id": entity.pk,
        "analysis_run_id": run.pk,
        "claim_text": text,
        "version": None,
        "platform": None,
        "availability": None,
        "evidence": {"start": 0, "end": len(quote), "quote": quote},
    }


def post_json(client, path, body):
    return client.post(path, data=json.dumps(body), content_type="application/json")


def test_claim_creation_requires_authentication_and_links_source(authenticated_client):
    entity, article, run = make_context()
    path = "/api/knowledge/claims"

    anonymous = post_json(Client(), path, {"claim_text": "Widget supports ARM."})
    assert anonymous.status_code == 401
    assert Client().get(f"/api/knowledge/entities/{entity.pk}/claims").status_code == 401

    created = post_json(authenticated_client, path, payload(entity, run, "Widget supports ARM."))
    assert created.status_code == 201
    assert created.json()["entity_id"] == entity.pk
    assert created.json()["source_article"]["id"] == article.pk
    assert created.json()["classification"] == "new"
    assert created.json()["supersedes_id"] is None


def test_contradictory_claim_appends_supersession_and_timeline_chain(authenticated_client):
    entity, article, run = make_context()
    path = "/api/knowledge/claims"
    first = post_json(authenticated_client, path, payload(entity, run, "Widget supports ARM."))
    second_payload = payload(entity, run, "Widget does not support ARM.")
    second = post_json(authenticated_client, path, second_payload)
    third = post_json(authenticated_client, path, payload(entity, run, "Widget supports ARM."))

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 201
    assert second.json()["classification"] == "contradiction"
    assert second.json()["supersedes_id"] == first.json()["id"]
    assert third.json()["classification"] == "contradiction"
    assert third.json()["supersedes_id"] == second.json()["id"]

    timeline = authenticated_client.get(f"/api/knowledge/entities/{entity.pk}/claims")
    assert timeline.status_code == 200
    claims = timeline.json()["items"]
    assert [claim["id"] for claim in claims] == [
        third.json()["id"], second.json()["id"], first.json()["id"]
    ]
    assert claims[0]["source_article"]["url"] == article.url
    assert claims[0]["supersedes_id"] == claims[1]["id"]
    assert claims[1]["supersedes_id"] == claims[2]["id"]
    assert claims[1]["superseded_by_ids"] == [claims[0]["id"]]
    assert claims[2]["superseded_by_ids"] == [claims[1]["id"]]


def test_claims_have_no_mutation_or_deletion_api(authenticated_client):
    entity, _article, run = make_context()
    created = post_json(authenticated_client, "/api/knowledge/claims", payload(entity, run, "Widget supports ARM."))
    claim_id = created.json()["id"]

    assert authenticated_client.patch(f"/api/knowledge/claims/{claim_id}", data="{}", content_type="application/json").status_code in (404, 405)
    assert authenticated_client.delete(f"/api/knowledge/claims/{claim_id}").status_code in (404, 405)
    assert authenticated_client.get(f"/api/knowledge/entities/{entity.pk}/claims").json()["items"][0]["claim_text"] == "Widget supports ARM."


def test_claim_model_and_queryset_reject_mutation_and_deletion():
    from delta_feed.knowledge.use_cases import record_claim

    entity, article, run = make_context()
    claim = record_claim(
        entity,
        {
            "claim_text": "Widget supports ARM.",
            "version": None,
            "platform": None,
            "availability": None,
            "evidence_start": 0,
            "evidence_end": len(article.body),
            "evidence_text": article.body,
        },
        run,
    )
    claim.claim_text = "rewritten"
    with pytest.raises(ValueError, match="append-only"):
        claim.save()
    with pytest.raises(ValueError, match="append-only"):
        claim.delete()
    with pytest.raises(ValueError, match="append-only"):
        type(claim).objects.filter(pk=claim.pk).update(claim_text="rewritten")
    with pytest.raises(ValueError, match="append-only"):
        type(claim).objects.filter(pk=claim.pk).delete()


def test_record_claim_classifies_and_persists_scope_and_run_provenance():
    from delta_feed.knowledge.use_cases import record_claim

    entity, article, run = make_context()
    claim = record_claim(
        entity,
        {
            "claim_text": "Widget supports ARM on Linux.",
            "version": "2.0",
            "platform": "Linux",
            "availability": "stable",
            "evidence_start": 0,
            "evidence_end": len(article.body),
            "evidence_text": article.body,
        },
        run,
    )
    claim.refresh_from_db()
    assert claim.entity_id == entity.pk
    assert claim.source_article_id == article.pk
    assert claim.analysis_run_id == run.pk
    assert claim.version == "2.0"
    assert claim.platform == "Linux"
    assert claim.availability == "stable"
    assert claim.classification == "new"
    assert claim.observed_at is not None


def test_duplicate_and_refinement_are_recorded_not_suppressed():
    from delta_feed.knowledge.use_cases import record_claim

    entity, article, run = make_context()
    common = {
        "version": None,
        "platform": None,
        "availability": None,
        "evidence_start": 0,
        "evidence_end": len(article.body),
        "evidence_text": article.body,
    }
    first = record_claim(entity, {**common, "claim_text": "Widget supports ARM."}, run)
    duplicate = record_claim(entity, {**common, "claim_text": "widget supports ARM"}, run)
    refinement = record_claim(
        entity, {**common, "claim_text": "Widget supports ARM on Linux."}, run
    )

    assert [first.classification, duplicate.classification, refinement.classification] == [
        "new",
        "duplicate",
        "refinement",
    ]
    assert Claim.objects.filter(entity=entity).count() == 3
    assert duplicate.supersedes_id is None
    assert refinement.supersedes_id is None
