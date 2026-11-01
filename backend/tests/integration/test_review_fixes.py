import json
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from delta_feed.analysis.contracts.extraction import EXTRACTION_SCHEMA_ID
from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.use_cases import extract_article, record_run
from delta_feed.content import rss
from delta_feed.content.models import Article, ArticleRevision, Source
from delta_feed.content.revisions import current_revision
from delta_feed.guides.models import GuideDefinition, GuideEntry, GuideProposal
from delta_feed.knowledge.models import Entity
from delta_feed.knowledge.use_cases import record_claim

pytestmark = pytest.mark.django_db


def public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def feed_response(xml: str):
    body = xml.encode()
    response = Mock()
    response.status_code = 200
    response.headers = {"Content-Length": str(len(body))}
    response.iter_content.return_value = [body]
    return response


def poll(source, xml, *, backfill=False):
    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=public_dns), patch(
        "delta_feed.content.rss.requests.Session.get", return_value=feed_response(xml)
    ):
        return rss.poll_rss_source({"source_id": source.pk, "backfill": backfill})


def make_source(name="Publisher"):
    return Source.objects.create(name=name, rss_feed_url="https://publisher.example/feed.xml")


def rss_item(link, *, guid="g1", title="T", desc="Body", pub="Tue, 03 Nov 2026 10:00:00 GMT"):
    pub_xml = f"<pubDate>{pub}</pubDate>" if pub else ""
    return (
        '<rss version="2.0"><channel><title>F</title><item>'
        f"<guid>{guid}</guid><title>{title}</title><link>{link}</link>"
        f"<description>{desc}</description>{pub_xml}</item></channel></rss>"
    )


@pytest.fixture
def user():
    return get_user_model().objects.create_user(username="reviewer", password="pw-pw-pw-pw-1")


@pytest.fixture
def client(user):
    client = Client()
    client.force_login(user)
    return client


# --- C1: link validation -------------------------------------------------------

@pytest.mark.parametrize(
    "link",
    ["javascript:alert(1)", "data:text/html,x", "JaVaScRiPt:alert(1)", "ftp://x.example/a"],
)
def test_rss_items_with_non_http_links_are_skipped_not_stored(link):
    feed_source = make_source()
    count = poll(feed_source, rss_item(link.replace("&", "&amp;")))
    assert count == 0
    assert Article.objects.count() == 0
    feed_source.refresh_from_db()
    assert "Skipped 1" in feed_source.last_error
    assert feed_source.consecutive_failures == 0


def test_manual_submission_rejects_non_http_urls(client):
    response = client.post(
        "/api/content/articles",
        data=json.dumps({"url": "javascript:alert(1)//x", "title": "t", "body": "b"}),
        content_type="application/json",
    )
    assert response.status_code == 422


# --- C2: SSRF / DNS pinning ----------------------------------------------------

@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "224.0.0.1",
     "0.0.0.0", "::1", "fe80::1", "fc00::1", "ff02::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1"],
)
def test_non_public_addresses_are_rejected(address):
    host = f"[{address}]" if ":" in address else address
    with pytest.raises(ValueError, match="public"):
        rss._resolve_public_http_url(f"http://{host}/feed")


def test_mixed_public_and_private_dns_answer_is_rejected():
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 80)),
    ]
    with patch("delta_feed.content.rss.socket.getaddrinfo", return_value=answers), pytest.raises(
        ValueError, match="public"
    ):
        rss._resolve_public_http_url("http://rebind.example/feed")


def test_connection_is_pinned_to_validated_ip_but_keeps_host_header():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["host"] = self.headers["Host"]
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    try:
        # The name does not resolve anywhere; only the pinned IP can be reached.
        import requests

        with requests.Session() as session:
            response = rss._http_get(session, f"http://pinned.invalid:{port}/feed", "127.0.0.1")
            assert response.content == b"ok"
    finally:
        thread.join(timeout=5)
        server.server_close()
    assert seen["host"] == f"pinned.invalid:{port}"


def test_each_redirect_hop_is_resolved_and_pinned_separately():
    first = Mock(status_code=302, headers={"Location": "https://second.example/feed"}, close=Mock())
    second = feed_response(rss_item("https://publisher.example/a"))
    pinned = []

    def fake_get(session, url, ip):
        pinned.append((url, ip))
        return first if len(pinned) == 1 else second

    answers = {
        "first.example": "93.184.216.34",
        "second.example": "93.184.216.35",
    }

    def dns(host, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (answers[host], 443))]

    with patch("delta_feed.content.rss.socket.getaddrinfo", side_effect=dns), patch(
        "delta_feed.content.rss._http_get", side_effect=fake_get
    ):
        rss._fetch_feed("https://first.example/feed")
    assert pinned == [
        ("https://first.example/feed", "93.184.216.34"),
        ("https://second.example/feed", "93.184.216.35"),
    ]


# --- misc RSS hardening --------------------------------------------------------

def test_plain_text_drops_script_and_style_contents():
    html = "<p>Hello</p><script>alert('x')</script><style>p{color:red}</style><b>world</b>"
    assert rss._plain_text(html) == "Hello world"


def test_missing_published_at_does_not_erase_known_date():
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/a", desc="v1"))
    first = Article.objects.get()
    assert first.source_published_at is not None
    poll(feed_source, rss_item("https://publisher.example/a", desc="v2", pub=None))
    first.refresh_from_db()
    assert first.source_published_at is not None
    assert first.current_version == 2


def test_item_without_date_is_stored_with_null_published_at():
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/a", pub=None))
    assert Article.objects.get().source_published_at is None


# --- M4: quiet backfill --------------------------------------------------------

def test_backfilled_articles_stay_out_of_today_and_remain_unread(client):
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/old", guid="old"), backfill=True)
    poll(feed_source, rss_item("https://publisher.example/new", guid="new"), backfill=False)

    today = client.get("/api/reader/feed").json()
    assert [item["url"] for item in today["items"]] == ["https://publisher.example/new"]
    backfill = client.get("/api/reader/feed?view=backfill").json()
    assert [item["url"] for item in backfill["items"]] == ["https://publisher.example/old"]
    assert backfill["items"][0]["is_backfill"] is True
    assert backfill["items"][0]["is_read"] is False
    assert client.get("/api/reader/feed?view=all").json()["total"] == 2


def test_replaying_a_backfilled_item_later_does_not_promote_it_to_today(client):
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/old"), backfill=True)
    poll(feed_source, rss_item("https://publisher.example/old", desc="edited"), backfill=False)
    assert client.get("/api/reader/feed").json()["total"] == 0


def test_explicit_manual_submission_of_a_backfilled_url_surfaces_it(client):
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/old"), backfill=True)
    client.post(
        "/api/content/articles",
        data=json.dumps({"url": "https://publisher.example/old", "title": "Mine", "body": "b"}),
        content_type="application/json",
    )
    assert client.get("/api/reader/feed").json()["total"] == 1


# --- M5: identity --------------------------------------------------------------

def test_manual_submission_of_feed_owned_url_appends_revision_without_duplicate(client):
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/a"))
    response = client.post(
        "/api/content/articles",
        data=json.dumps({"url": "https://publisher.example/a", "title": "Mine", "body": "Notes"}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json()["created"] is False
    assert Article.objects.count() == 1
    assert Article.objects.get().revisions.count() == 2


def test_feed_adopts_manual_article_then_manual_resubmit_is_same_article(client):
    client.post(
        "/api/content/articles",
        data=json.dumps({"url": "https://publisher.example/a", "title": "Mine", "body": "Notes"}),
        content_type="application/json",
    )
    feed_source = make_source()
    poll(feed_source, rss_item("https://publisher.example/a"))
    client.post(
        "/api/content/articles",
        data=json.dumps({"url": "https://publisher.example/a", "title": "Mine 2", "body": "More"}),
        content_type="application/json",
    )
    assert Article.objects.count() == 1
    article = Article.objects.get()
    assert article.source_id == feed_source.pk
    assert list(article.revisions.values_list("version", flat=True)) == [1, 2, 3]


# --- M7: feed bounded, no N+1 --------------------------------------------------

def test_feed_is_paginated_and_returns_excerpts_not_bodies(client, user):
    for index in range(7):
        Article.objects.create(url=f"https://example.org/{index}", title=f"T{index}", body="x" * 5000)
    page = client.get("/api/reader/feed?limit=3&offset=3").json()
    assert page["total"] == 7
    assert (page["limit"], page["offset"], page["has_more"]) == (3, 3, True)
    assert len(page["items"]) == 3
    assert "body" not in page["items"][0]
    assert len(page["items"][0]["excerpt"]) == 300
    assert client.get("/api/reader/feed?limit=3&offset=6").json()["has_more"] is False
    assert client.get("/api/reader/feed?limit=1000").status_code == 422
    assert client.get("/api/reader/feed?offset=-1").status_code == 422


def test_feed_query_count_is_constant_and_includes_source_name(client):
    feed_source = make_source("Named source")
    for index in range(2):
        Article.objects.create(
            source=feed_source, url=f"https://example.org/a{index}", title="t", body="b"
        )
    with CaptureQueriesContext(connection) as small:
        client.get("/api/reader/feed")
    for index in range(10):
        Article.objects.create(url=f"https://example.org/m{index}", title="t", body="b")
    with CaptureQueriesContext(connection) as large:
        data = client.get("/api/reader/feed?view=all&limit=100").json()
    assert len(large) == len(small)
    names = {item["url"]: item["source_name"] for item in data["items"]}
    assert names["https://example.org/a0"] == "Named source"
    assert names["https://example.org/m0"] is None


# --- M2 / M3: claim evidence and run status -----------------------------------

def make_article(body="Widget supports ARM."):
    return Article.objects.create(url="https://example.org/w", title="W", body=body)


def test_claim_spans_validate_against_the_analysed_revision_not_current_text():
    entity = Entity.objects.create(name="Widget", type="software")
    article = make_article()
    revision = current_revision(article)
    run = record_run(
        source_article=article,
        article_revision=revision,
        status=AnalysisRun.Status.COMPLETED,
        model_version="m",
        prompt_version="p",
    )
    # The article is later revised; spans from the analysed text remain valid.
    ArticleRevision.objects.create(
        article=article, version=2, title="W", body="Totally different", content_hash="x" * 64
    )
    Article.objects.filter(pk=article.pk).update(body="Totally different", current_version=2)
    run.refresh_from_db()
    run.source_article.refresh_from_db()
    claim = record_claim(
        entity,
        {
            "claim_text": "Widget supports ARM.",
            "evidence_start": 0,
            "evidence_end": 20,
            "evidence_text": "Widget supports ARM.",
        },
        run,
    )
    assert claim.analysis_run.article_revision_id == revision.pk


def test_record_run_rejects_revision_of_another_article():
    other = Article.objects.create(url="https://example.org/o", title="O", body="o")
    with pytest.raises(ValueError, match="belong"):
        record_run(
            source_article=make_article(),
            article_revision=current_revision(other),
            model_version="m",
            prompt_version="p",
        )


@pytest.mark.parametrize("status", [AnalysisRun.Status.RUNNING, AnalysisRun.Status.FAILED])
def test_claims_are_only_accepted_from_completed_runs(client, status):
    entity = Entity.objects.create(name="Widget", type="software")
    run = record_run(
        source_article=make_article(), status=status, model_version="m", prompt_version="p"
    )
    response = client.post(
        "/api/knowledge/claims",
        data=json.dumps(
            {
                "entity_id": entity.pk,
                "analysis_run_id": run.pk,
                "claim_text": "Widget supports ARM.",
                "evidence": {"start": 0, "end": 6, "quote": "Widget"},
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 409
    assert entity.claims.count() == 0


def test_claim_from_legacy_run_without_revision_is_rejected(client):
    entity = Entity.objects.create(name="Widget", type="software")
    run = AnalysisRun.objects.create(
        source_article=make_article(),
        status=AnalysisRun.Status.COMPLETED,
        model_version="m",
        prompt_version="p",
    )
    with pytest.raises(ValueError, match="revision"):
        record_claim(
            entity,
            {"claim_text": "c", "evidence_start": 0, "evidence_end": 6, "evidence_text": "Widget"},
            run,
        )


def test_extract_article_pins_run_to_revision_it_analysed():
    class Adapter:
        model_version = "fake"

        def analyze(self, prompt, schema):
            return {"schema_id": EXTRACTION_SCHEMA_ID, "entities": [], "claims": []}

    article = make_article()
    run, _ = extract_article(source_article=article, adapter=Adapter())
    assert run.article_revision.body == article.body
    assert run.article_revision.version == article.current_version


# --- M6: proposal uniqueness ---------------------------------------------------

def test_every_matching_entry_in_a_guide_gets_its_own_update_proposal(user):
    guide = GuideDefinition.objects.create(owner=user, title="G", purpose="p", audience="a")
    entity = Entity.objects.create(name="Rivet", type="software")
    entries = [
        GuideEntry.objects.create(guide=guide, entity=entity, entity_name="Rivet", suitability=text)
        for text in ("one", "two")
    ]
    baseline = Article.objects.create(url="https://example.org/b", title="b", body="Rivet supports Linux.")
    done = AnalysisRun.Status.COMPLETED
    record_claim(
        entity,
        {"claim_text": "Rivet supports Linux.", "evidence_start": 0,
         "evidence_end": len(baseline.body), "evidence_text": baseline.body},
        record_run(source_article=baseline, status=done, model_version="m", prompt_version="p"),
    )
    text = "Rivet supports Linux with ARM support."
    article = Article.objects.create(url="https://example.org/c", title="c", body=text)
    record_claim(
        entity,
        {"claim_text": text, "evidence_start": 0, "evidence_end": len(text), "evidence_text": text},
        record_run(source_article=article, status=done, model_version="m", prompt_version="p"),
    )
    proposals = GuideProposal.objects.filter(proposal_type="update")
    assert {proposal.target_entry_id for proposal in proposals} == {e.pk for e in entries}


# --- minor hardening -----------------------------------------------------------

def test_login_is_throttled_after_repeated_failures(user):
    cache.clear()
    client = Client()
    attempt = lambda password: client.post(
        "/api/accounts/login",
        data=json.dumps({"username": "reviewer", "password": password}),
        content_type="application/json",
    )
    assert [attempt("wrong").status_code for _ in range(5)] == [401] * 5
    assert attempt("wrong").status_code == 429
    assert attempt("pw-pw-pw-pw-1").status_code == 429
    cache.clear()
    assert attempt("pw-pw-pw-pw-1").status_code == 200


def test_deleting_entity_with_claims_returns_conflict_not_500(client):
    entity = Entity.objects.create(name="Widget", type="software")
    run = record_run(
        source_article=make_article(),
        status=AnalysisRun.Status.COMPLETED,
        model_version="m",
        prompt_version="p",
    )
    record_claim(
        entity,
        {"claim_text": "c", "evidence_start": 0, "evidence_end": 6, "evidence_text": "Widget"},
        run,
    )
    response = client.delete(f"/api/knowledge/entities/{entity.pk}")
    assert response.status_code == 409
    assert Entity.objects.filter(pk=entity.pk).exists()
    free = Entity.objects.create(name="Free", type="software")
    assert client.delete(f"/api/knowledge/entities/{free.pk}").status_code == 204


def _import_settings(env):
    return subprocess.run(
        [sys.executable, "-c", "import delta_feed.config.settings as s; print(s.DEBUG, s.SESSION_COOKIE_SECURE, s.CSRF_COOKIE_SECURE)"],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin", "PYTHONPATH": "src", **env},
        check=False,
    )


def test_production_settings_fail_fast_without_a_real_secret_key():
    assert _import_settings({}).returncode != 0
    assert _import_settings({"DJANGO_SECRET_KEY": "short"}).returncode != 0
    ok = _import_settings({"DJANGO_SECRET_KEY": "k" * 60})
    assert ok.returncode == 0
    assert ok.stdout.split() == ["False", "True", "True"]
    dev = _import_settings({"DJANGO_DEBUG": "true"})
    assert dev.returncode == 0
    assert dev.stdout.split() == ["True", "False", "False"]
