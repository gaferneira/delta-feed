import json

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client

from delta_feed.accounts.models import ReaderProfile, TopicSelection
from delta_feed.content.models import Source
from delta_feed.jobs.models import Job
from delta_feed.knowledge.models import Topic

pytestmark = pytest.mark.django_db

HA_FEED = "https://www.home-assistant.io/atom.xml"
ESPHOME_FEED = "https://github.com/esphome/esphome/releases.atom"
AI_FEED = "https://simonwillison.net/atom/everything/"


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="reader", password="correct-horse-battery")


@pytest.fixture
def client(user):
    client = Client()
    client.force_login(user)
    return client


def post_json(client, path, payload=None):
    return client.post(path, data=json.dumps(payload or {}), content_type="application/json")


def complete(client, topics, feed_urls):
    return post_json(client, "/api/onboarding/complete", {"topics": topics, "feed_urls": feed_urls})


def test_session_reports_onboarding_state(client, user):
    assert client.get("/api/accounts/session").json() == {
        "authenticated": True,
        "onboarding_complete": False,
    }
    ReaderProfile.objects.create(user=user, onboarding_completed_at="2026-01-01T00:00:00Z")
    assert client.get("/api/accounts/session").json()["onboarding_complete"] is True
    assert Client().get("/api/accounts/session").json() == {
        "authenticated": False,
        "onboarding_complete": False,
    }


def test_profile_without_completion_timestamp_is_incomplete(client, user):
    ReaderProfile.objects.create(user=user)
    assert client.get("/api/accounts/session").json()["onboarding_complete"] is False


def test_users_created_after_migration_start_incomplete():
    created = get_user_model().objects.create_superuser(username="admin", password="correct-horse-battery")
    assert not ReaderProfile.objects.filter(user=created).exists()


@pytest.mark.django_db(transaction=True)
def test_migration_marks_existing_users_complete():
    executor = MigrationExecutor(connection)
    executor.migrate([("accounts", "0002_readerprofile_topicselection")])
    old_apps = executor.loader.project_state([("accounts", "0002_readerprofile_topicselection")]).apps
    old_apps.get_model("auth", "User").objects.create(username="legacy")
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes("accounts"))
    profile = ReaderProfile.objects.get(user__username="legacy")
    assert profile.onboarding_completed_at is not None


def test_state_lists_packs_and_current_selection(client, user):
    topic = Topic.objects.create(slug="home-automation", title="Home automation")
    TopicSelection.objects.create(user=user, topic=topic)
    body = client.get("/api/onboarding").json()
    slugs = [pack["slug"] for pack in body["packs"]]
    assert {"home-automation", "ai", "developer-tooling"} <= set(slugs)
    pack = next(pack for pack in body["packs"] if pack["slug"] == "home-automation")
    assert {"name", "feed_url", "homepage_url"} == set(pack["feeds"][0])
    assert HA_FEED in [feed["feed_url"] for feed in pack["feeds"]]
    assert body["selected_topics"] == ["home-automation"]


def test_complete_creates_topics_selection_sources_and_one_backfill(client, user):
    response = complete(client, ["home-automation"], [HA_FEED, ESPHOME_FEED])
    assert response.status_code == 200
    topic = Topic.objects.get(slug="home-automation")
    assert topic.title == "Home automation"
    assert list(TopicSelection.objects.filter(user=user).values_list("topic__slug", flat=True)) == ["home-automation"]
    assert set(topic.sources.values_list("rss_feed_url", flat=True)) == {HA_FEED, ESPHOME_FEED}
    assert Source.objects.count() == 2
    jobs = Job.objects.filter(type="rss.poll")
    assert jobs.count() == 2
    assert all(job.payload["backfill"] is True for job in jobs)
    assert client.get("/api/accounts/session").json()["onboarding_complete"] is True


def test_resubmitting_is_idempotent_and_does_not_backfill_again(client, user):
    first = complete(client, ["home-automation"], [HA_FEED])
    stamp = ReaderProfile.objects.get(user=user).onboarding_completed_at
    second = complete(client, ["home-automation"], [HA_FEED])
    assert (first.status_code, second.status_code) == (200, 200)
    assert Topic.objects.count() == 1
    assert TopicSelection.objects.count() == 1
    assert Source.objects.count() == 1
    assert Job.objects.filter(type="rss.poll").count() == 1
    assert Topic.objects.get().sources.count() == 1
    assert ReaderProfile.objects.get(user=user).onboarding_completed_at == stamp


def test_existing_source_is_attached_without_a_second_backfill(client):
    existing = Source.objects.create(name="My own name", rss_feed_url=HA_FEED)
    assert complete(client, ["home-automation"], [HA_FEED]).status_code == 200
    assert Source.objects.get().pk == existing.pk
    assert Topic.objects.get().sources.get() == existing
    assert Job.objects.count() == 0


def test_topic_without_feeds_and_empty_completion_are_allowed(client, user):
    assert complete(client, ["ai"], []).status_code == 200
    assert Source.objects.count() == 0 and TopicSelection.objects.count() == 1
    other = get_user_model().objects.create_user(username="other", password="correct-horse-battery")
    other_client = Client()
    other_client.force_login(other)
    assert complete(other_client, [], []).status_code == 200
    assert ReaderProfile.objects.get(user=other).onboarding_completed_at is not None


def test_two_users_share_topics_and_sources(client):
    complete(client, ["home-automation"], [HA_FEED])
    other = get_user_model().objects.create_user(username="other", password="correct-horse-battery")
    other_client = Client()
    other_client.force_login(other)
    assert complete(other_client, ["home-automation"], [HA_FEED]).status_code == 200
    assert Topic.objects.count() == 1 and Source.objects.count() == 1
    assert TopicSelection.objects.count() == 2


def test_unknown_pack_is_rejected_and_nothing_changes(client, user):
    response = complete(client, ["home-automation", "nope"], [])
    assert response.status_code == 400
    assert Topic.objects.count() == 0 and TopicSelection.objects.count() == 0
    assert client.get("/api/accounts/session").json()["onboarding_complete"] is False


@pytest.mark.parametrize(
    "feed_url",
    ["https://evil.example/feed.xml", AI_FEED],  # unknown, and a real feed from an unchosen pack
)
def test_feed_outside_the_chosen_packs_is_rejected(client, feed_url):
    response = complete(client, ["home-automation"], [HA_FEED, feed_url])
    assert response.status_code == 400
    assert Source.objects.count() == 0 and Topic.objects.count() == 0 and Job.objects.count() == 0


def test_conflicting_source_name_rolls_everything_back(client):
    Source.objects.create(name="Home Assistant blog", rss_feed_url="https://other.example/feed.xml")
    response = complete(client, ["home-automation"], [ESPHOME_FEED, HA_FEED])
    assert response.status_code == 409
    assert Source.objects.count() == 1 and Topic.objects.count() == 0 and Job.objects.count() == 0
    assert not ReaderProfile.objects.exists()


def test_invalid_pack_directory_gives_503_without_changes(client, settings, tmp_path):
    (tmp_path / "broken.toml").write_text("slug = 1", encoding="utf-8")
    settings.STARTER_PACKS_DIR = tmp_path
    assert client.get("/api/onboarding").status_code == 503
    assert complete(client, [], []).status_code == 503
    assert not ReaderProfile.objects.exists()


def test_skip_marks_complete_and_changes_nothing_else(client, user):
    response = post_json(client, "/api/onboarding/skip")
    assert response.status_code == 200
    assert ReaderProfile.objects.get(user=user).onboarding_completed_at is not None
    assert not Topic.objects.exists() and not TopicSelection.objects.exists()
    assert not Source.objects.exists() and not Job.objects.exists()
    assert post_json(client, "/api/onboarding/skip").status_code == 200


def test_skip_keeps_an_existing_selection(client, user):
    complete(client, ["home-automation"], [HA_FEED])
    post_json(client, "/api/onboarding/skip")
    assert TopicSelection.objects.filter(user=user).count() == 1
    assert Source.objects.count() == 1


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/onboarding"),
        ("post", "/api/onboarding/complete"),
        ("post", "/api/onboarding/skip"),
    ],
)
def test_onboarding_requires_authentication(method, path):
    response = getattr(Client(), method)(
        path, **({"data": "{}", "content_type": "application/json"} if method == "post" else {})
    )
    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/api/onboarding/complete", "/api/onboarding/skip"])
def test_onboarding_mutations_enforce_csrf(user, path):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    response = client.post(path, data="{}", content_type="application/json")
    assert response.status_code == 403
    assert not ReaderProfile.objects.exists()
    token = client.get("/api/accounts/csrf").json()["csrf_token"]
    ok = client.post(path, data="{}", content_type="application/json", headers={"X-CSRFToken": token})
    assert ok.status_code == 200
