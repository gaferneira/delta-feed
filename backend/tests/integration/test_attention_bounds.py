import json
import socket
import time
from datetime import timedelta
from email.utils import formatdate
from io import StringIO
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from delta_feed.content import rss
from delta_feed.content.models import Article, Source
from delta_feed.content.use_cases import poll_delay, register_source, schedule_due_polls
from delta_feed.jobs.models import Job
from delta_feed.jobs.services import claim_job, execute_claimed_job

pytestmark = pytest.mark.django_db


def pubdate(days_ago):
    return formatdate(time.time() - days_ago * 86400, usegmt=True)


def feed_xml(*items):
    """items: (guid, days_ago or None) pairs."""
    body = "".join(
        f"<item><guid>{guid}</guid><title>Title {guid}</title>"
        f"<link>https://publisher.example/{guid}</link><description>Body {guid}</description>"
        + (f"<pubDate>{pubdate(days)}</pubDate>" if days is not None else "")
        + "</item>"
        for guid, days in items
    )
    return f'<rss version="2.0"><channel><title>F</title>{body}</channel></rss>'


def poll(source, xml, *, backfill):
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Length": str(len(xml))}
    response.iter_content.return_value = [xml.encode()]
    public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("delta_feed.content.rss.socket.getaddrinfo", return_value=public), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=response
    ):
        return rss.poll_rss_source({"source_id": source.pk, "backfill": backfill})


@pytest.fixture
def feed_source():
    return Source.objects.create(name="Publisher", rss_feed_url="https://publisher.example/feed.xml")


# --- bounded backfill ---------------------------------------------------------

def test_backfill_imports_only_entries_inside_the_window(feed_source, settings):
    settings.BACKFILL_DAYS = 30
    result = poll(
        feed_source, feed_xml(("new", 1), ("month", 29), ("old", 31), ("ancient", 900)), backfill=True
    )
    assert set(Article.objects.values_list("external_id", flat=True)) == {"new", "month"}
    assert result["imported"] == 2
    assert result["skipped_outside_window"] == 2
    assert result["skipped_over_cap"] == 0
    assert Article.objects.filter(is_backfill=False).count() == 0


def test_backfill_item_cap_keeps_the_newest_entries(feed_source, settings):
    settings.BACKFILL_MAX_ITEMS = 2
    result = poll(
        feed_source, feed_xml(("d5", 5), ("d1", 1), ("d3", 3), ("d2", 2)), backfill=True
    )
    assert set(Article.objects.values_list("external_id", flat=True)) == {"d1", "d2"}
    assert result["imported"] == 2
    assert result["skipped_over_cap"] == 2


def test_backfill_undated_entries_only_fill_the_remaining_cap_in_feed_order(feed_source, settings):
    settings.BACKFILL_MAX_ITEMS = 3
    result = poll(
        feed_source,
        feed_xml(("u1", None), ("u2", None), ("dated", 2), ("u3", None)),
        backfill=True,
    )
    assert set(Article.objects.values_list("external_id", flat=True)) == {"dated", "u1", "u2"}
    assert result["skipped_over_cap"] == 1


def test_backfill_poll_stores_the_cutoff_and_job_result_is_recorded(settings):
    settings.BACKFILL_DAYS = 30
    source, job_id = register_source(
        name="Recorded", rss_feed_url="https://publisher.example/recorded.xml"
    )
    before = timezone.now()
    response = Mock()
    response.status_code = 200
    xml = feed_xml(("a", 1), ("b", 60))
    response.headers = {"Content-Length": str(len(xml))}
    response.iter_content.return_value = [xml.encode()]
    public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
    with patch("delta_feed.content.rss.socket.getaddrinfo", return_value=public), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=response
    ):
        job = claim_job(job_id=job_id)
        assert execute_claimed_job(job) is True
    job.refresh_from_db()
    assert job.result["imported"] == 1
    assert job.result["skipped_outside_window"] == 1
    source.refresh_from_db()
    assert abs((source.backfill_cutoff - (before - timedelta(days=30))).total_seconds()) < 60


# --- recurring polls and the backfill cutoff ----------------------------------

def test_recurring_poll_does_not_import_history_the_backfill_trimmed(feed_source, settings):
    """The critical case: the same feed is seen again; trimmed old items must not become news."""
    settings.BACKFILL_DAYS = 30
    settings.BACKFILL_MAX_ITEMS = 20
    items = [("recent", 2), ("old-1", 100), ("old-2", 400)]
    poll(feed_source, feed_xml(*items), backfill=True)
    assert set(Article.objects.values_list("external_id", flat=True)) == {"recent"}

    result = poll(feed_source, feed_xml(*items), backfill=False)

    assert set(Article.objects.values_list("external_id", flat=True)) == {"recent"}
    assert result["imported"] == 1  # the stored article is revisited, not re-created
    assert result["skipped_outside_window"] == 2
    assert Article.objects.filter(is_backfill=False).count() == 0


def test_recurring_poll_imports_genuinely_new_entries_as_current(feed_source, settings):
    settings.BACKFILL_DAYS = 30
    poll(feed_source, feed_xml(("recent", 2), ("old", 100)), backfill=True)

    result = poll(
        feed_source, feed_xml(("fresh", 0), ("recent", 2), ("old", 100), ("undated", None)),
        backfill=False,
    )

    fresh = Article.objects.get(external_id="fresh")
    assert fresh.is_backfill is False
    assert Article.objects.get(external_id="undated").is_backfill is False
    assert Article.objects.get(external_id="recent").is_backfill is True  # intent is fixed
    assert not Article.objects.filter(external_id="old").exists()
    assert result["skipped_outside_window"] == 1


def test_entries_the_item_cap_trimmed_are_history_for_later_polls(feed_source, settings):
    """A source with more recent posts than the cap must not flood Today on the next poll."""
    settings.BACKFILL_DAYS = 30
    settings.BACKFILL_MAX_ITEMS = 20
    items = [(f"p{day}", day / 2 + 0.1) for day in range(30)]  # 30 entries, all within the window
    poll(feed_source, feed_xml(*items), backfill=True)
    assert Article.objects.count() == 20

    result = poll(feed_source, feed_xml(*items), backfill=False)

    assert Article.objects.count() == 20
    assert not Article.objects.filter(external_id__in=[guid for guid, _ in items[20:]]).exists()
    assert result["skipped_outside_window"] == 10
    assert Article.objects.filter(is_backfill=False).count() == 0


def test_genuinely_new_entry_after_a_cap_trimmed_backfill_is_current(feed_source, settings):
    settings.BACKFILL_DAYS = 30
    settings.BACKFILL_MAX_ITEMS = 2
    items = [("d1", 1), ("d2", 2), ("d3", 3), ("d4", 4)]
    poll(feed_source, feed_xml(*items), backfill=True)

    poll(feed_source, feed_xml(("fresh", 0), *items), backfill=False)

    assert Article.objects.get(external_id="fresh").is_backfill is False
    assert not Article.objects.filter(external_id__in=["d3", "d4"]).exists()


def test_cutoff_stays_at_the_window_when_the_cap_trims_nothing(feed_source, settings):
    settings.BACKFILL_DAYS = 30
    settings.BACKFILL_MAX_ITEMS = 20
    before = timezone.now()
    poll(feed_source, feed_xml(("a", 1), ("b", 5)), backfill=True)
    feed_source.refresh_from_db()
    assert abs((feed_source.backfill_cutoff - (before - timedelta(days=30))).total_seconds()) < 60


def test_cutoff_rises_to_the_newest_trimmed_entry_when_the_cap_trims(feed_source, settings):
    settings.BACKFILL_DAYS = 30
    settings.BACKFILL_MAX_ITEMS = 1
    poll(feed_source, feed_xml(("d1", 1), ("d5", 5)), backfill=True)
    feed_source.refresh_from_db()
    assert timezone.now() - feed_source.backfill_cutoff < timedelta(days=5, minutes=1)


def test_source_without_a_cutoff_is_anchored_to_registration_on_a_recurring_poll(feed_source, settings):
    settings.BACKFILL_DAYS = 30
    assert feed_source.backfill_cutoff is None
    poll(feed_source, feed_xml(("fresh", 0), ("old", 90)), backfill=False)
    assert set(Article.objects.values_list("external_id", flat=True)) == {"fresh"}
    feed_source.refresh_from_db()
    assert feed_source.backfill_cutoff is not None


# --- scheduler ----------------------------------------------------------------

def polled_source(name, *, minutes_ago, failures=0):
    return Source.objects.create(
        name=name,
        rss_feed_url=f"https://publisher.example/{name}.xml",
        last_fetch_at=timezone.now() - timedelta(minutes=minutes_ago),
        backfill_cutoff=timezone.now() - timedelta(days=30),
        consecutive_failures=failures,
    )


def test_scheduler_enqueues_due_sources_only(settings):
    settings.RSS_POLL_INTERVAL_MINUTES = 30
    due = polled_source("due", minutes_ago=31)
    polled_source("recent", minutes_ago=5)

    assert schedule_due_polls() == [due.pk]
    job = Job.objects.get()
    assert job.type == "rss.poll"
    assert job.payload == {"source_id": due.pk, "backfill": False}


def test_scheduler_never_duplicates_a_pending_or_leased_job(settings):
    settings.RSS_POLL_INTERVAL_MINUTES = 30
    due = polled_source("due", minutes_ago=90)

    assert schedule_due_polls() == [due.pk]
    assert schedule_due_polls() == []  # pending
    claim_job()
    assert schedule_due_polls() == []  # leased
    assert Job.objects.count() == 1

    Job.objects.update(status=Job.Status.SUCCEEDED)
    assert schedule_due_polls() == [due.pk]  # finished jobs do not block the next poll


def test_scheduler_backs_off_after_failures_and_caps_the_delay(settings):
    settings.RSS_POLL_INTERVAL_MINUTES = 30
    polled_source("failing", minutes_ago=45, failures=1)  # waits 60 min
    ready = polled_source("ready", minutes_ago=70, failures=1)
    assert schedule_due_polls() == [ready.pk]

    interval = timedelta(minutes=30)
    assert poll_delay(0, interval) == timedelta(minutes=30)
    assert poll_delay(2, interval) == timedelta(minutes=120)
    assert poll_delay(40, interval) == timedelta(hours=24)


def test_never_fetched_source_without_cutoff_gets_a_backfill_poll(feed_source):
    assert schedule_due_polls() == [feed_source.pk]
    assert Job.objects.get().payload["backfill"] is True


def test_sources_without_a_feed_url_are_not_scheduled():
    Source.objects.create(name="Manual only")
    assert schedule_due_polls() == []


def test_run_worker_once_schedules_due_work_then_runs_it(settings):
    settings.RSS_POLL_INTERVAL_MINUTES = 30
    due = polled_source("due", minutes_ago=60)
    out = StringIO()
    with patch(
        "delta_feed.jobs.management.commands.run_worker.execute_claimed_job"
    ) as execute:
        call_command("run_worker", "--once", stdout=out)
    assert Job.objects.get().payload["source_id"] == due.pk
    execute.assert_called_once()
    assert "Scheduled RSS polls for 1 source" in out.getvalue()


# --- import status ------------------------------------------------------------

@pytest.fixture
def client():
    user = get_user_model().objects.create_user(username="reader", password="correct-horse-battery")
    client = Client()
    client.force_login(user)
    return client


def test_import_status_requires_authentication():
    assert Client().get("/api/content/import-status").status_code == 401


def test_import_status_reports_progress_and_an_idle_worker(client):
    done = polled_source("done", minutes_ago=1)
    register_source(name="waiting", rss_feed_url="https://publisher.example/waiting.xml")
    Job.objects.update(created_at=timezone.now() - timedelta(minutes=10))
    assert done.pk

    data = client.get("/api/content/import-status").json()

    assert data["sources_total"] == 2
    assert data["sources_fetched"] == 1
    assert data["pending_jobs"] == 1
    assert data["oldest_pending_seconds"] >= 600
    assert data["worker_seen_recently"] is False


def test_import_status_sees_a_worker_that_recently_handled_a_job(client):
    register_source(name="waiting", rss_feed_url="https://publisher.example/waiting.xml")
    claim_job()
    data = client.get("/api/content/import-status").json()
    assert data["worker_seen_recently"] is True
    assert json.dumps(data)  # plain JSON only
