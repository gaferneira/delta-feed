import json
import socket
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
import requests
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from delta_feed.content.models import Article, ArticleRevision, Source
from delta_feed.jobs.models import Job
from delta_feed.jobs.services import claim_job, run_job
from delta_feed.reader.models import ReadState

pytestmark = pytest.mark.django_db

RSS_BODY = b'''<?xml version="1.0"?><rss version="2.0"><channel><title>Feed</title>
<item><guid>entry-1</guid><title>First release</title><link>https://publisher.example/a1</link>
<description>Article body</description><pubDate>Tue, 03 Nov 2026 10:00:00 GMT</pubDate></item>
</channel></rss>'''


def source(**overrides):
    return Source.objects.create(
        name=overrides.pop("name", "Publisher"),
        rss_feed_url=overrides.pop("rss_feed_url", "https://publisher.example/feed.xml"),
        **overrides,
    )


def mocked_response(body=RSS_BODY, *, headers=None):
    response = Mock()
    response.status_code = 200
    response.headers = headers or {"Content-Length": str(len(body))}
    response.iter_content.return_value = [body]
    response.close = Mock()
    return response


def public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def test_rss_poll_creates_article_revision_quietly_and_marks_source_healthy():
    feed_source = source()
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=mocked_response()
    ) as get:
        from delta_feed.content.rss import poll_rss_source

        poll_rss_source({"source_id": feed_source.pk, "backfill": True})

    article = Article.objects.get(source=feed_source)
    assert article.url == "https://publisher.example/a1"
    assert article.title == "First release"
    assert article.body == "Article body"
    assert article.current_version == 1
    assert ArticleRevision.objects.get(article=article).version == 1
    assert not ReadState.objects.filter(article=article).exists()
    feed_source.refresh_from_db()
    assert feed_source.last_fetch_at is not None
    assert feed_source.last_error == ""
    assert feed_source.consecutive_failures == 0
    assert get.call_args.kwargs["allow_redirects"] is False
    assert get.call_args.kwargs["stream"] is True
    assert get.call_args.kwargs["timeout"]


def test_malformed_feed_fails_job_and_records_source_health():
    feed_source = source()
    response = mocked_response(b"not an rss document")
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=response
    ):
        from delta_feed.content.rss import poll_rss_source

        with pytest.raises(ValueError, match="feed"):
            poll_rss_source({"source_id": feed_source.pk, "backfill": True})

    feed_source.refresh_from_db()
    assert feed_source.consecutive_failures == 1
    assert feed_source.last_error
    assert Article.objects.count() == 0


def test_oversized_and_slow_rss_responses_are_rejected_with_finite_http_bounds():
    feed_source = source()
    too_large = mocked_response(b"x", headers={"Content-Length": "999999999"})
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=too_large
    ) as get:
        from delta_feed.content.rss import poll_rss_source

        with pytest.raises(ValueError, match="size"):
            poll_rss_source({"source_id": feed_source.pk, "backfill": True})
    assert get.call_args.kwargs["timeout"] == (3, 5)

    slow = mocked_response()
    slow.iter_content.side_effect = requests.Timeout("read timed out")
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=slow
    ), pytest.raises(requests.Timeout):
        poll_rss_source({"source_id": feed_source.pk, "backfill": True})

    feed_source.refresh_from_db()
    assert feed_source.consecutive_failures == 2


def test_ssrf_private_target_is_rejected_before_http_request():
    feed_source = source(rss_feed_url="http://127.0.0.1/private-feed")
    with patch("delta_feed.content.rss.requests.Session.get") as get:
        from delta_feed.content.rss import poll_rss_source

        with pytest.raises(ValueError, match="public"):
            poll_rss_source({"source_id": feed_source.pk, "backfill": True})
    get.assert_not_called()
    feed_source.refresh_from_db()
    assert feed_source.consecutive_failures == 1


def test_job_lease_claim_prevents_second_claim_until_expiry():
    job = Job.objects.create(
        type="rss.poll",
        payload={"source_id": source().pk, "backfill": True},
        handler_name="content.poll_rss",
    )

    first = claim_job()
    second = claim_job()

    assert first.pk == job.pk
    assert second is None
    job.refresh_from_db()
    assert job.status == Job.Status.RUNNING
    assert job.attempt_count == 1
    assert job.lease_expires_at > timezone.now()


def test_concurrent_claim_attempts_issue_at_most_one_lease():
    from django.db import connection

    job = Job.objects.create(
        type="rss.poll",
        payload={"source_id": source().pk},
        handler_name="content.poll_rss",
    )

    if connection.vendor == "sqlite":
        # SQLite's test database is single-writer and cannot model two simultaneous
        # lease updates. Keep the behavioral guarantee deterministic here; the
        # threaded branch below exercises actual row-lock contention on PostgreSQL.
        claims = [claim_job(), claim_job()]
    else:
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections

        start = Barrier(2)

        def claim_simultaneously():
            close_old_connections()
            try:
                start.wait(timeout=5)
                return claim_job()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: claim_simultaneously(), range(2)))

    assert sum(claim is not None for claim in claims) == 1
    job.refresh_from_db()
    assert job.status == Job.Status.RUNNING
    assert job.attempt_count == 1


def test_failed_job_is_retried_after_bounded_exponential_backoff(monkeypatch):
    job = Job.objects.create(type="rss.poll", payload={}, handler_name="content.poll_rss")
    from delta_feed.jobs import services

    monkeypatch.setitem(services.HANDLERS, "content.poll_rss", lambda payload: (_ for _ in ()).throw(RuntimeError("temporary")))

    assert run_job(job.pk) is False
    job.refresh_from_db()
    assert job.status == Job.Status.PENDING
    assert job.attempt_count == 1
    assert job.run_after >= timezone.now() + timedelta(seconds=29)
    assert job.lease_expires_at is None
    assert "temporary" in job.last_error


def test_authenticated_source_onboarding_enqueues_quiet_backfill_idempotently():
    user = get_user_model().objects.create_user(username="feed-owner")
    client = Client()
    client.force_login(user)
    payload = {
        "name": "New publisher",
        "rss_feed_url": "https://publisher.example/feed.xml",
        "homepage_url": "https://publisher.example/",
    }

    response = client.post(
        "/api/content/sources",
        data=json.dumps(payload),
        content_type="application/json",
    )
    assert response.status_code == 201
    source_id = response.json()["source_id"]
    job = Job.objects.get(payload__source_id=source_id)
    assert job.type == "rss.poll"
    assert job.handler_name == "content.poll_rss"
    assert job.payload["backfill"] is True
    assert Article.objects.count() == 0

    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=mocked_response()
    ):
        assert run_job(job.pk) is True
        assert run_job(job.pk) is False
    assert Article.objects.filter(source_id=source_id).count() == 1
    assert ArticleRevision.objects.filter(article__source_id=source_id).count() == 1
    assert not ReadState.objects.filter(article__source_id=source_id).exists()


def test_failed_job_becomes_terminal_after_bounded_attempt_budget(monkeypatch):
    job = Job.objects.create(type="rss.poll", payload={}, handler_name="content.poll_rss")
    from delta_feed.jobs import services

    monkeypatch.setitem(
        services.HANDLERS,
        "content.poll_rss",
        lambda payload: (_ for _ in ()).throw(RuntimeError("still broken")),
    )
    for _ in range(services.MAX_ATTEMPTS):
        Job.objects.filter(pk=job.pk).update(run_after=timezone.now() - timedelta(seconds=1))
        assert run_job(job.pk) is False
    job.refresh_from_db()
    assert job.status == Job.Status.FAILED
    assert job.attempt_count == services.MAX_ATTEMPTS


def test_older_revision_is_retained_without_replacing_current_snapshot():
    feed_source = source()

    def rss(published, title, body):
        return f'''<rss version="2.0"><channel><title>Feed</title><item>
        <guid>same-guid</guid><title>{title}</title><link>https://publisher.example/same</link>
        <description>{body}</description><pubDate>{published}</pubDate>
        </item></channel></rss>'''.encode()

    from delta_feed.content.rss import poll_rss_source

    responses = [
        mocked_response(rss("Tue, 03 Nov 2026 10:00:00 GMT", "First", "v1")),
        mocked_response(rss("Wed, 04 Nov 2026 10:00:00 GMT", "Newer", "v2")),
        mocked_response(rss("Mon, 02 Nov 2026 10:00:00 GMT", "Delayed replay", "old")),
    ]
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", side_effect=responses
    ):
        poll_rss_source({"source_id": feed_source.pk, "backfill": True})
        poll_rss_source({"source_id": feed_source.pk, "backfill": True})
        poll_rss_source({"source_id": feed_source.pk, "backfill": True})

    article = Article.objects.get(source=feed_source)
    assert article.current_version == 2
    assert article.title == "Newer"
    assert article.body == "v2"
    assert list(article.revisions.values_list("version", flat=True)) == [1, 2, 3]


def test_private_redirect_target_is_rejected_before_following_redirect():
    feed_source = source()
    redirect = mocked_response(b"", headers={"Location": "http://10.0.0.1/admin"})
    redirect.status_code = 302
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=redirect
    ) as get:
        from delta_feed.content.rss import poll_rss_source

        with pytest.raises(ValueError, match="public"):
            poll_rss_source({"source_id": feed_source.pk, "backfill": True})
    assert get.call_count == 1


def test_authenticated_source_list_returns_frontend_health_shape():
    user = get_user_model().objects.create_user(username="source-reader")
    client = Client()
    client.force_login(user)
    fetched_at = timezone.now()
    first = source(
        name="Healthy publisher",
        last_fetch_at=fetched_at,
        last_error="",
        consecutive_failures=0,
    )
    second = source(
        name="Failing publisher",
        rss_feed_url="https://other.example/rss.xml",
        last_error="timeout",
        consecutive_failures=2,
    )

    response = client.get("/api/content/sources")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": first.pk,
            "name": "Healthy publisher",
            "rss_feed_url": "https://publisher.example/feed.xml",
            "last_fetch_at": fetched_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "last_error": "",
            "consecutive_failures": 0,
        },
        {
            "id": second.pk,
            "name": "Failing publisher",
            "rss_feed_url": "https://other.example/rss.xml",
            "last_fetch_at": None,
            "last_error": "timeout",
            "consecutive_failures": 2,
        },
    ]


def test_source_list_requires_authentication():
    response = Client().get("/api/content/sources")
    assert response.status_code == 401


def test_source_onboarding_requires_authentication():
    response = Client().post(
        "/api/content/sources",
        data=json.dumps({"name": "Nope", "rss_feed_url": "https://publisher.example/feed.xml"}),
        content_type="application/json",
    )
    assert response.status_code == 401
