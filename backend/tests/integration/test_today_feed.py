from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from delta_feed.content.models import Article, Source
from delta_feed.reader.models import ReadState, SaveState

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="reader", password="correct-horse-battery")


@pytest.fixture
def client(user):
    client = Client()
    client.force_login(user)
    return client


def make_article(source, slug, *, hours_ago=1, backfill=False, published_days_ago=None):
    article = Article.objects.create(
        source=source,
        url=f"https://example.org/{slug}",
        title=f"Title {slug}",
        body=f"Body {slug}",
        is_backfill=backfill,
        source_published_at=(
            timezone.now() - timedelta(days=published_days_ago)
            if published_days_ago is not None else None
        ),
    )
    # created_at is auto_now_add; age it to the requested discovery time.
    Article.objects.filter(pk=article.pk).update(
        created_at=timezone.now() - timedelta(hours=hours_ago)
    )
    return article


def sources(*names):
    return [Source.objects.create(name=name) for name in names]


def urls(data):
    return [item["url"].rsplit("/", 1)[1] for item in data["items"]]


def test_today_uses_discovery_time_not_publication_time(client):
    (feed,) = sources("A")
    make_article(feed, "just-found-old-post", hours_ago=2, published_days_ago=40)
    make_article(feed, "found-yesterday", hours_ago=30, published_days_ago=0)
    make_article(feed, "earlier-import", hours_ago=2, backfill=True)

    data = client.get("/api/reader/feed?view=today").json()

    assert urls(data) == ["just-found-old-post"]
    assert data["more_count"] == 0
    assert data["items"][0]["discovered_at"]


def test_today_budget_and_per_source_cap_with_overflow_via_more(client, settings):
    settings.TODAY_BUDGET = 4
    settings.TODAY_PER_SOURCE_CAP = 2
    a, b, c = sources("A", "B", "C")
    for index in range(5):
        make_article(a, f"a{index}", hours_ago=1 + index)
    make_article(b, "b0", hours_ago=7)
    make_article(c, "c0", hours_ago=8)

    data = client.get("/api/reader/feed?view=today").json()

    assert urls(data) == ["a0", "a1", "b0", "c0"]  # selected by rounds, shown newest first
    assert data["total"] == 4
    assert data["more_count"] == 3
    assert data["has_more"] is False

    more = client.get("/api/reader/feed?view=today&more=true").json()
    assert urls(more) == ["a2", "a3", "a4"]
    assert more["more_count"] == 3


def test_today_is_recency_ordered_and_diverse(client, settings):
    settings.TODAY_BUDGET = 3
    settings.TODAY_PER_SOURCE_CAP = 3
    prolific, quiet = sources("Prolific", "Quiet")
    for index in range(4):
        make_article(prolific, f"p{index}", hours_ago=1 + index)
    make_article(quiet, "q0", hours_ago=10)

    data = client.get("/api/reader/feed?view=today").json()

    # The quiet source's only article beats the prolific source's third.
    assert urls(data) == ["p0", "p1", "q0"]


def test_manual_submissions_are_never_capped(client, settings):
    settings.TODAY_BUDGET = 12
    settings.TODAY_PER_SOURCE_CAP = 1
    for index in range(3):
        make_article(None, f"manual{index}", hours_ago=index + 1)
    data = client.get("/api/reader/feed?view=today").json()
    assert len(data["items"]) == 3
    assert data["more_count"] == 0


def test_read_and_save_state_survive_in_both_today_lists(client, user, settings):
    settings.TODAY_BUDGET = 1
    (feed,) = sources("A")
    shown = make_article(feed, "shown", hours_ago=1)
    hidden = make_article(feed, "hidden", hours_ago=2)
    ReadState.objects.create(user=user, article=shown, is_read=True)
    SaveState.objects.create(user=user, article=hidden, is_saved=True)

    first = client.get("/api/reader/feed?view=today").json()["items"][0]
    rest = client.get("/api/reader/feed?view=today&more=true").json()["items"][0]

    assert (first["is_read"], first["is_saved"]) == (True, False)
    assert (rest["is_read"], rest["is_saved"]) == (False, True)
    assert first["source_name"] == "A"


def test_all_and_backfill_views_still_list_everything(client, settings):
    settings.TODAY_BUDGET = 1
    (feed,) = sources("A")
    for index in range(3):
        make_article(feed, f"n{index}", hours_ago=index + 1)
    make_article(feed, "old", hours_ago=500, backfill=True)

    assert client.get("/api/reader/feed?view=all").json()["total"] == 4
    assert urls(client.get("/api/reader/feed?view=backfill").json()) == ["old"]
    assert client.get("/api/reader/feed?view=backfill").json()["more_count"] == 0
