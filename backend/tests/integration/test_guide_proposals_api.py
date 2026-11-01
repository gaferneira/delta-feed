import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.use_cases import record_run
from delta_feed.content.models import Article
from delta_feed.guides.models import (
    GuideDefinition,
    GuideEntry,
    GuideProposal,
    GuideRevision,
)
from delta_feed.knowledge.models import Claim, Entity

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner():
    return get_user_model().objects.create_user(
        username="proposal-owner", password="password"
    )


@pytest.fixture
def client(owner):
    authenticated = Client()
    authenticated.force_login(owner)
    return authenticated


def proposal_fixture(
    owner,
    *,
    body="Rivet runs on Linux and is actively maintained.",
    criteria=None,
    article_url="https://example.org/rivet",
):
    guide = GuideDefinition.objects.create(
        owner=owner,
        title="Small server tools",
        purpose="Choose practical tools for a small server.",
        audience="Home server operators",
        eligibility_criteria=criteria or ["Linux"],
    )
    article = Article.objects.create(url=article_url, title="Rivet release", body=body)
    run = record_run(
        source_article=article,
        status=AnalysisRun.Status.COMPLETED,
        model_version="test-model",
        prompt_version="test-prompt",
    )
    entity = Entity.objects.create(name="Rivet", type="software")
    return guide, article, run, entity


def generate(entity, run):
    from delta_feed.guides.use_cases import generate_guide_proposals_for_entity

    return generate_guide_proposals_for_entity(entity, run)


def post_json(client, path, payload=None):
    return client.post(
        path,
        data=json.dumps(payload or {}),
        content_type="application/json",
    )


def test_entity_matching_eligibility_creates_pending_reviewable_proposal(owner):
    guide, article, run, entity = proposal_fixture(owner)

    proposals = generate(entity, run)

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.guide == guide
    assert proposal.entity == entity
    assert proposal.analysis_run == run
    assert proposal.source_article == article
    assert proposal.status == "pending"
    assert proposal.proposed_entry["entity_name"] == "Rivet"
    assert proposal.evidence[0]["url"] == article.url
    assert proposal.reasoning


def test_entity_not_matching_any_eligibility_criteria_creates_no_proposal(owner):
    guide, _, run, entity = proposal_fixture(
        owner,
        body="Rivet is a useful command-line tool.",
        criteria=["home automation"],
    )

    proposals = generate(entity, run)

    assert proposals == []
    assert guide.proposals.count() == 0


def test_accepting_proposal_creates_entry_with_source_evidence_preserved(client, owner):
    guide, article, run, entity = proposal_fixture(owner)
    proposal = generate(entity, run)[0]

    response = post_json(client, f"/api/guides/proposals/{proposal.pk}/accept")

    assert response.status_code == 200
    entry = GuideEntry.objects.get(guide=guide)
    assert entry.entity_name == "Rivet"
    assert entry.evidence == proposal.evidence
    assert entry.evidence[0]["article_id"] == article.pk
    assert entry.evidence[0]["analysis_run_id"] == run.pk
    assert entry.review_metadata["proposal_status"] == "accepted"
    assert entry.personal_prose == ""
    proposal.refresh_from_db()
    assert proposal.status == "accepted"
    assert proposal.accepted_entry_id == entry.pk


def test_rejecting_proposal_does_not_create_entry(client, owner):
    guide, _, run, entity = proposal_fixture(owner)
    proposal = generate(entity, run)[0]

    response = post_json(client, f"/api/guides/proposals/{proposal.pk}/reject")

    assert response.status_code == 200
    proposal.refresh_from_db()
    assert proposal.status == "rejected"
    assert GuideEntry.objects.filter(guide=guide).count() == 0


def test_double_accept_does_not_create_a_duplicate_entry(client, owner):
    guide, _, run, entity = proposal_fixture(owner)
    proposal = generate(entity, run)[0]
    path = f"/api/guides/proposals/{proposal.pk}/accept"

    first = post_json(client, path)
    second = post_json(client, path)

    assert first.status_code == 200
    assert second.status_code == 409
    assert GuideEntry.objects.filter(guide=guide).count() == 1


def test_pending_proposal_list_returns_only_owners_pending_proposals(client, owner):
    first_guide, _, first_run, first_entity = proposal_fixture(owner)
    pending = generate(first_entity, first_run)[0]
    _, _, second_run, second_entity = proposal_fixture(
        owner,
        body="Rivet runs on Linux.",
        criteria=["Linux"],
        article_url="https://example.org/rivet-follow-up",
    )
    rejected_proposals = generate(second_entity, second_run)
    for proposal in rejected_proposals:
        post_json(client, f"/api/guides/proposals/{proposal.pk}/reject")

    response = client.get("/api/guides/proposals")

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [pending.pk]
    assert response.json()["items"][0]["guide_id"] == first_guide.pk


def test_proposal_endpoints_require_authentication(owner):
    _guide, _, run, entity = proposal_fixture(owner)
    proposal = generate(entity, run)[0]
    anonymous = Client()

    responses = [
        anonymous.get("/api/guides/proposals"),
        post_json(anonymous, f"/api/guides/proposals/{proposal.pk}/accept"),
        post_json(anonymous, f"/api/guides/proposals/{proposal.pk}/reject"),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401]


def make_claim_for_tracked_entry(owner, *, claim_text, availability=None):
    from delta_feed.knowledge.use_cases import record_claim

    guide = GuideDefinition.objects.create(
        owner=owner,
        title="Small server tools",
        purpose="Choose practical tools for a small server.",
        audience="Home server operators",
    )
    entity = Entity.objects.create(name="Rivet", type="software")
    entry = GuideEntry.objects.create(
        guide=guide,
        entity=entity,
        entity_name=entity.name,
        suitability="Use Rivet for a small server.",
        caveats=["Review maintenance status."],
        personal_prose="My original note; preserve it.",
    )
    GuideRevision.objects.create(
        entry=entry,
        version=entry.revision,
        snapshot={
            "suitability": entry.suitability,
            "caveats": entry.caveats,
            "personal_prose": entry.personal_prose,
            "is_retired": entry.is_retired,
        },
        changed_by=owner,
    )
    baseline_article = Article.objects.create(
        url=f"https://example.org/rivet-baseline-{Article.objects.count()}",
        title="Rivet baseline",
        body="Rivet supports Linux.",
    )
    baseline_run = record_run(
        source_article=baseline_article,
        status=AnalysisRun.Status.COMPLETED,
        model_version="test-model",
        prompt_version="test-prompt",
    )
    record_claim(
        entity,
        {
            "claim_text": "Rivet supports Linux.",
            "evidence_start": 0,
            "evidence_end": len(baseline_article.body),
            "evidence_text": baseline_article.body,
        },
        baseline_run,
    )

    source = claim_text
    article = Article.objects.create(
        url=f"https://example.org/rivet-change-{Article.objects.count()}",
        title="Rivet change",
        body=source,
    )
    run = record_run(
        source_article=article,
        status=AnalysisRun.Status.COMPLETED,
        model_version="test-model",
        prompt_version="test-prompt",
    )
    claim = record_claim(
        entity,
        {
            "claim_text": claim_text,
            "availability": availability,
            "evidence_start": 0,
            "evidence_end": len(source),
            "evidence_text": source,
        },
        run,
    )
    return guide, entry, claim


def test_refinement_on_tracked_entity_creates_pending_update_proposal(owner):
    guide, entry, claim = make_claim_for_tracked_entry(
        owner, claim_text="Rivet supports Linux with ARM support."
    )

    proposal = GuideProposal.objects.get(guide=guide, entity=claim.entity)

    assert claim.classification == Claim.Classification.REFINEMENT
    assert proposal.proposal_type == GuideProposal.ProposalType.UPDATE
    assert proposal.status == GuideProposal.Status.PENDING
    assert proposal.target_entry == entry
    assert proposal.proposed_entry["suitability"] == claim.claim_text
    assert proposal.evidence[0]["quote"] == claim.evidence_text
    entry.refresh_from_db()
    assert entry.suitability == "Use Rivet for a small server."


def test_contradiction_on_tracked_entity_creates_pending_warning_proposal(owner):
    guide, entry, claim = make_claim_for_tracked_entry(
        owner, claim_text="Rivet does not support Linux."
    )

    proposal = GuideProposal.objects.get(guide=guide, entity=claim.entity)

    assert claim.classification == Claim.Classification.CONTRADICTION
    assert proposal.proposal_type == GuideProposal.ProposalType.WARNING
    assert proposal.status == GuideProposal.Status.PENDING
    assert proposal.target_entry == entry
    assert proposal.evidence[0]["quote"] == claim.evidence_text
    assert proposal.proposed_entry["warning"]
    entry.refresh_from_db()
    assert entry.suitability == "Use Rivet for a small server."


def test_discontinued_marker_on_tracked_entity_creates_retire_proposal(owner):
    guide, entry, claim = make_claim_for_tracked_entry(
        owner,
        claim_text="Rivet has been discontinued.",
        availability="discontinued",
    )

    proposal = GuideProposal.objects.get(guide=guide, entity=claim.entity)

    assert proposal.proposal_type == GuideProposal.ProposalType.RETIRE
    assert proposal.status == GuideProposal.Status.PENDING
    assert proposal.target_entry == entry
    assert proposal.evidence[0]["quote"] == claim.evidence_text
    entry.refresh_from_db()
    assert entry.is_retired is False


def test_accepting_update_warning_and_retire_proposals_applies_reviewed_effects(
    client, owner
):
    scenarios = [
        ("Rivet supports Linux with ARM support.", None, "update"),
        ("Rivet does not support Linux.", None, "warning"),
        ("Rivet has been discontinued.", "discontinued", "retire"),
    ]

    for claim_text, availability, proposal_type in scenarios:
        guide, entry, claim = make_claim_for_tracked_entry(
            owner, claim_text=claim_text, availability=availability
        )
        proposal = GuideProposal.objects.get(guide=guide, entity=claim.entity)
        assert proposal.proposal_type == proposal_type
        assert proposal.status == GuideProposal.Status.PENDING
        response = post_json(client, f"/api/guides/proposals/{proposal.pk}/accept")

        assert response.status_code == 200
        entry.refresh_from_db()
        proposal.refresh_from_db()
        assert proposal.status == GuideProposal.Status.ACCEPTED
        assert proposal.accepted_entry_id == entry.pk
        assert entry.revision == 2
        assert entry.revisions.count() == 2
        assert entry.revisions.get(version=1).snapshot["suitability"] == (
            "Use Rivet for a small server."
        )
        assert entry.personal_prose == "My original note; preserve it."
        assert claim.evidence_text in str(entry.evidence)
        if proposal_type == "update":
            # Merged, not overwritten: existing editorial text is preserved.
            assert entry.suitability.startswith("Use Rivet for a small server.")
            assert entry.suitability.endswith(claim.claim_text)
            assert entry.caveats == ["Review maintenance status."]
        elif proposal_type == "warning":
            assert entry.suitability == "Use Rivet for a small server."
            assert any("potentially outdated" in note for note in entry.caveats)
            assert entry.revisions.get(version=2).snapshot["suitability"] == entry.suitability
        else:
            assert entry.is_retired is True
            assert entry.suitability == "Use Rivet for a small server."
            assert entry.revisions.get(version=2).snapshot["is_retired"] is True


def test_refinement_without_a_tracked_guide_entry_creates_no_proposal(owner):
    from delta_feed.knowledge.use_cases import record_claim

    _guide, _article, run, entity = proposal_fixture(owner)
    article = run.source_article
    record_claim(
        entity,
        {
            "claim_text": "Rivet supports Linux.",
            "evidence_start": 0,
            "evidence_end": len(article.body),
            "evidence_text": article.body,
        },
        run,
    )
    record_claim(
        entity,
        {
            "claim_text": "Rivet supports Linux with ARM support.",
            "evidence_start": 0,
            "evidence_end": len(article.body),
            "evidence_text": article.body,
        },
        run,
    )

    assert GuideProposal.objects.filter(entity=entity).count() == 0


def test_update_proposal_accept_requires_authentication(owner):
    _guide, _entry, claim = make_claim_for_tracked_entry(
        owner, claim_text="Rivet supports Linux with ARM support."
    )
    proposal = GuideProposal.objects.get(entity=claim.entity)

    response = post_json(Client(), f"/api/guides/proposals/{proposal.pk}/accept")

    assert response.status_code == 401


def test_accepting_update_rejects_stale_entry_revision(client, owner):
    _guide, entry, claim = make_claim_for_tracked_entry(
        owner, claim_text="Rivet supports Linux with ARM support."
    )
    proposal = GuideProposal.objects.get(entity=claim.entity)
    changed = client.patch(
        f"/api/guides/entries/{entry.pk}",
        data=json.dumps({"expected_revision": 1, "caveats": ["New manual caveat"]}),
        content_type="application/json",
    )

    response = post_json(client, f"/api/guides/proposals/{proposal.pk}/accept")

    assert changed.status_code == 200
    assert response.status_code == 409
    proposal.refresh_from_db()
    entry.refresh_from_db()
    assert proposal.status == GuideProposal.Status.PENDING
    assert entry.revision == 2
    assert entry.caveats == ["New manual caveat"]
