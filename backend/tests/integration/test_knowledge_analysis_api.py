import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delta_feed.analysis.models import AnalysisRun
from delta_feed.content.models import Article

pytestmark = pytest.mark.django_db


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def patch_json(client, path, payload):
    return client.patch(path, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def client():
    user = get_user_model().objects.create_user(
        username="knowledge-owner", password="password"
    )
    authenticated = Client()
    authenticated.force_login(user)
    return authenticated


def entity_payload():
    return {
        "name": "Example Tool",
        "type": "software",
        "canonical_url": "https://example.org/tool",
        "slug": "example-tool",
        "identifiers": {"repository": "owner/example-tool"},
        "aliases": ["Example", "ExTool"],
    }


def test_entity_crud_requires_authentication_and_supports_authenticated_crud(client):
    anonymous = Client()
    assert anonymous.get("/api/knowledge/entities").status_code == 401
    assert anonymous.get("/api/knowledge/entities/1").status_code == 401
    assert post_json(anonymous, "/api/knowledge/entities", entity_payload()).status_code == 401
    assert patch_json(anonymous, "/api/knowledge/entities/1", {"name": "Nope"}).status_code == 401
    assert anonymous.delete("/api/knowledge/entities/1").status_code == 401

    created = post_json(client, "/api/knowledge/entities", entity_payload())
    assert created.status_code == 201
    entity = created.json()
    assert entity["name"] == "Example Tool"
    assert entity["aliases"] == ["Example", "ExTool"]

    listed = client.get("/api/knowledge/entities")
    assert listed.status_code == 200
    assert listed.json()["items"][0]["id"] == entity["id"]

    fetched = client.get(f"/api/knowledge/entities/{entity['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["canonical_url"] == "https://example.org/tool"

    updated = patch_json(
        client, f"/api/knowledge/entities/{entity['id']}", {"name": "Example Tool 2"}
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Example Tool 2"

    deleted = client.delete(f"/api/knowledge/entities/{entity['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/knowledge/entities/{entity['id']}").status_code == 404


def test_exact_identifier_match_endpoint_returns_entity_or_none(client):
    created = post_json(client, "/api/knowledge/entities", entity_payload())
    assert created.status_code == 201
    entity = created.json()

    hit = post_json(
        client,
        "/api/knowledge/entities/match",
        {"identifiers": {"repository": "owner/example-tool"}},
    )
    assert hit.status_code == 200
    assert hit.json()["entity"]["id"] == entity["id"]

    miss = post_json(
        client,
        "/api/knowledge/entities/match",
        {"identifiers": {"slug": "unknown-tool"}},
    )
    assert miss.status_code == 200
    assert miss.json()["entity"] is None

    alias_is_not_a_strong_identifier = post_json(
        client,
        "/api/knowledge/entities/match",
        {"identifiers": {"alias": "Example"}},
    )
    assert alias_is_not_a_strong_identifier.status_code == 200
    assert alias_is_not_a_strong_identifier.json()["entity"] is None

    empty = post_json(client, "/api/knowledge/entities/match", {"identifiers": {}})
    assert empty.status_code == 200
    assert empty.json()["entity"] is None

    assert post_json(
        Client(), "/api/knowledge/entities/match", {"identifiers": {}}
    ).status_code == 401


def test_analysis_run_records_provenance_fields():
    from delta_feed.analysis.use_cases import record_run

    article = Article.objects.create(
        url="https://example.org/article", title="A title", body="Article body"
    )
    run = record_run(
        source_article=article,
        status=AnalysisRun.Status.RUNNING,
        model_version="model-v1",
        prompt_version="extract-v1",
    )

    stored = AnalysisRun.objects.get(pk=run.pk)
    assert stored.source_article_id == article.pk
    assert stored.started_at is not None
    assert stored.completed_at is None
    assert stored.status == AnalysisRun.Status.RUNNING
    assert stored.model_version == "model-v1"
    assert stored.prompt_version == "extract-v1"
    assert stored.schema_version == "delta-feed.extraction.v1"
