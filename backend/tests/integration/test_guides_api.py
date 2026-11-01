import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delta_feed.guides.models import GuideDefinition, GuideEntry, GuideRevision

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        username="guide-owner", password="password"
    )


@pytest.fixture
def client(user):
    authenticated = Client()
    authenticated.force_login(user)
    return authenticated


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def patch_json(client, path, payload):
    return client.patch(path, data=json.dumps(payload), content_type="application/json")


def guide_payload():
    return {
        "title": "Choosing a deployment tool",
        "purpose": "Deploy small services reliably",
        "audience": "Operators maintaining a small home server",
        "topic_links": ["self-hosting", "deployment"],
        "eligibility_criteria": ["Maintained", "Works on Linux"],
        "sections": [
            {
                "title": "Simple deployments",
                "description": "Start with a small footprint.",
            },
            {"title": "Operational fit", "description": "Check backup and rollback."},
        ],
    }


def entry_payload():
    return {
        "entity_name": "Example Deploy",
        "suitability": "Good for a single maintained host.",
        "requirements": ["Linux", "SSH access"],
        "caveats": ["Requires routine updates."],
        "evidence": [{"url": "https://example.org/docs", "note": "Install guide"}],
        "review_metadata": {"status": "reviewed", "freshness": "current"},
        "personal_prose": "  I tried this last winter — keep my notes exactly.\n",
    }


def create_guide(client):
    response = post_json(client, "/api/guides/definitions", guide_payload())
    assert response.status_code == 201
    return response.json()["id"]


def create_entry(client, guide_id):
    response = post_json(
        client, f"/api/guides/definitions/{guide_id}/entries", entry_payload()
    )
    assert response.status_code == 201
    return response.json()


def test_create_guide_and_add_structured_entry(client):
    guide_id = create_guide(client)
    guide = client.get(f"/api/guides/definitions/{guide_id}")
    assert guide.status_code == 200
    assert guide.json()["purpose"] == guide_payload()["purpose"]
    assert guide.json()["topic_links"] == ["self-hosting", "deployment"]
    assert [section["title"] for section in guide.json()["sections"]] == [
        "Simple deployments",
        "Operational fit",
    ]

    entry = create_entry(client, guide_id)
    assert entry["entity_name"] == "Example Deploy"
    assert entry["requirements"] == ["Linux", "SSH access"]
    assert entry["personal_prose"] == entry_payload()["personal_prose"]
    assert entry["revision"] == 1
    assert GuideDefinition.objects.count() == 1
    assert GuideEntry.objects.count() == 1
    assert GuideRevision.objects.count() == 1


def test_edit_entry_preserves_personal_prose_and_appends_revision(client):
    guide_id = create_guide(client)
    entry = create_entry(client, guide_id)

    edited = post_json(
        client,
        f"/api/guides/entries/{entry['id']}/edit",
        {
            "expected_revision": 1,
            "suitability": "Better for a small, single-host service.",
            "requirements": ["Linux"],
            "caveats": ["Plan for upgrades."],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["revision"] == 2
    assert edited.json()["suitability"] == "Better for a small, single-host service."
    assert edited.json()["personal_prose"] == entry_payload()["personal_prose"]

    revisions = client.get(f"/api/guides/entries/{entry['id']}/revisions")
    assert revisions.status_code == 200
    assert [revision["version"] for revision in revisions.json()["items"]] == [1, 2]
    assert (
        revisions.json()["items"][0]["snapshot"]["personal_prose"]
        == entry_payload()["personal_prose"]
    )
    assert (
        revisions.json()["items"][1]["snapshot"]["personal_prose"]
        == entry_payload()["personal_prose"]
    )
    assert GuideRevision.objects.filter(entry_id=entry["id"]).count() == 2


def test_edit_entry_rejects_stale_expected_revision_with_409(client):
    guide_id = create_guide(client)
    entry = create_entry(client, guide_id)
    current = post_json(
        client,
        f"/api/guides/entries/{entry['id']}/edit",
        {"expected_revision": 1, "suitability": "First update"},
    )
    stale = post_json(
        client,
        f"/api/guides/entries/{entry['id']}/edit",
        {"expected_revision": 1, "suitability": "Stale update"},
    )

    assert current.status_code == 200
    assert stale.status_code == 409
    assert GuideEntry.objects.get(pk=entry["id"]).suitability == "First update"
    assert GuideRevision.objects.filter(entry_id=entry["id"]).count() == 2


def test_guide_definitions_and_entries_support_crud(client):
    guide_id = create_guide(client)
    listed = client.get("/api/guides/definitions")
    assert listed.status_code == 200
    assert [guide["id"] for guide in listed.json()["items"]] == [guide_id]

    updated_guide = patch_json(
        client,
        f"/api/guides/definitions/{guide_id}",
        {"audience": "Experienced operators"},
    )
    assert updated_guide.status_code == 200
    assert updated_guide.json()["audience"] == "Experienced operators"

    entry = create_entry(client, guide_id)
    fetched_entry = client.get(f"/api/guides/entries/{entry['id']}")
    assert fetched_entry.status_code == 200
    assert fetched_entry.json()["id"] == entry["id"]

    edited = patch_json(
        client,
        f"/api/guides/entries/{entry['id']}",
        {"expected_revision": 1, "caveats": ["Edited caveat"]},
    )
    assert edited.status_code == 200
    assert edited.json()["caveats"] == ["Edited caveat"]

    retired = client.delete(f"/api/guides/entries/{entry['id']}?expected_revision=2")
    assert retired.status_code == 204
    assert GuideEntry.objects.get(pk=entry["id"]).is_retired is True
    assert GuideRevision.objects.filter(entry_id=entry["id"]).count() == 3

    deleted_guide = client.delete(f"/api/guides/definitions/{guide_id}")
    assert deleted_guide.status_code == 204
    assert GuideDefinition.objects.get(pk=guide_id).is_archived is True
    assert GuideRevision.objects.filter(entry_id=entry["id"]).count() == 3


def test_guide_endpoints_require_authentication():
    anonymous = Client()
    checks = [
        anonymous.get("/api/guides/definitions"),
        post_json(anonymous, "/api/guides/definitions", guide_payload()),
        anonymous.get("/api/guides/definitions/1"),
        patch_json(anonymous, "/api/guides/definitions/1", {"title": "Nope"}),
        anonymous.delete("/api/guides/definitions/1"),
        post_json(anonymous, "/api/guides/definitions/1/entries", entry_payload()),
        anonymous.get("/api/guides/entries/1"),
        patch_json(anonymous, "/api/guides/entries/1", {"expected_revision": 1}),
        post_json(anonymous, "/api/guides/entries/1/edit", {"expected_revision": 1}),
        anonymous.delete("/api/guides/entries/1"),
        anonymous.get("/api/guides/entries/1/revisions"),
    ]
    assert [response.status_code for response in checks] == [401] * len(checks)
