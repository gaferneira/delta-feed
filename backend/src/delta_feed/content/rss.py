import calendar
import hashlib
import ipaddress
import socket
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import quote, urljoin, urlsplit

import feedparser
import requests
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.poolmanager import PoolManager

from delta_feed.content.models import Article, ArticleRevision, Source
from delta_feed.content.urls import safe_http_url

MAX_FEED_BYTES = 1_048_576
MAX_REDIRECTS = 3
CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 5
TOTAL_FETCH_SECONDS = 15


class _TextExtractor(HTMLParser):
    """Collect visible text; script/style contents are discarded, never kept as text."""

    _SKIPPED = frozenset({"script", "style"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIPPED:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIPPED and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def _plain_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value or "")
    parser.close()
    return " ".join(" ".join(parser.parts).split())


class InvalidEntryLink(ValueError):
    """An RSS item carries a link that must not be stored or rendered."""


def _is_public_address(address) -> bool:
    if address.version == 6 and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    return bool(address.is_global) and not (
        address.is_multicast
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


def _resolve_public_http_url(url: str) -> str:
    """Validate an RSS URL and return one public IP literal to pin the connection to.

    Every resolved address must be public; a mixed answer is rejected so an
    attacker-controlled name cannot offer a public address and a private one.
    """
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("RSS URL must be an absolute public HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("Credentialed RSS URLs are not permitted")
    host = parsed.hostname.rstrip(".")
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(result[4][0].split("%", 1)[0])
                for result in socket.getaddrinfo(
                    host, parsed.port or (443 if parsed.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            ]
        except (OSError, ValueError) as exc:
            raise ValueError("RSS host could not be resolved safely") from exc
    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise ValueError("RSS destination must resolve only to public IP addresses")
    return str(addresses[0])


def _validate_public_http_url(url: str) -> None:
    _resolve_public_http_url(url)


def _pinned_pool_classes(pinned_ip: str):
    """Pool classes whose sockets connect to ``pinned_ip`` only.

    The connection keeps ``host`` as the original name, so the Host header, SNI
    and certificate verification still use the hostname; only the TCP connect
    target is fixed to the address that passed validation, closing the DNS
    rebinding window between validation and connect.
    """

    def pin(base):
        class Pinned(base):
            def _new_conn(self):
                original = self._dns_host
                self._dns_host = pinned_ip
                try:
                    return super()._new_conn()
                finally:
                    self._dns_host = original

        return Pinned

    class PinnedHTTPPool(HTTPConnectionPool):
        ConnectionCls = pin(HTTPConnection)

    class PinnedHTTPSPool(HTTPSConnectionPool):
        ConnectionCls = pin(HTTPSConnection)

    return {"http": PinnedHTTPPool, "https": PinnedHTTPSPool}


class _PinnedAdapter(HTTPAdapter):
    def __init__(self, pinned_ip: str):
        self._pinned_ip = pinned_ip
        super().__init__(max_retries=0)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize, block=block, **pool_kwargs
        )
        self.poolmanager.pool_classes_by_scheme = _pinned_pool_classes(self._pinned_ip)


def _http_get(session: requests.Session, url: str, pinned_ip: str) -> requests.Response:
    session.trust_env = False  # ignore proxy env vars that would bypass pinning
    adapter = _PinnedAdapter(pinned_ip)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session.get(
        url,
        headers={"User-Agent": "DeltaFeed/0.1 (+RSS polling)"},
        timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
        allow_redirects=False,
        stream=True,
    )


def _fetch_feed(url: str) -> bytes:
    current_url = url
    deadline = time.monotonic() + TOTAL_FETCH_SECONDS
    for redirect_number in range(MAX_REDIRECTS + 1):
        # Re-resolved and re-validated on every redirect hop, then pinned.
        pinned_ip = _resolve_public_http_url(current_url)
        session = requests.Session()
        try:
            response = _http_get(session, current_url, pinned_ip)
        except BaseException:
            session.close()
            raise
        try:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location")
                if not location or redirect_number >= MAX_REDIRECTS:
                    raise ValueError("RSS redirect limit exceeded or invalid redirect")
                current_url = urljoin(current_url, location)
                continue
            response.raise_for_status()
            length = response.headers.get("Content-Length")
            if length:
                try:
                    if int(length) > MAX_FEED_BYTES:
                        raise ValueError("RSS response exceeds size limit")
                except ValueError as exc:
                    if "size limit" in str(exc):
                        raise
                    raise ValueError("Invalid RSS Content-Length") from exc
            chunks = []
            total = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if time.monotonic() > deadline:
                    raise requests.Timeout("RSS total fetch deadline exceeded")
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_FEED_BYTES:
                    raise ValueError("RSS response exceeds size limit")
                chunks.append(chunk)
            if time.monotonic() > deadline:
                raise requests.Timeout("RSS total fetch deadline exceeded")
            return b"".join(chunks)
        finally:
            response.close()
            session.close()
    raise ValueError("RSS redirect limit exceeded")


def _published_at(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed[:6]), tz=UTC)


def _entry_content(entry) -> tuple[str, str, str, str, datetime | None]:
    raw_link = (entry.get("link") or "").strip()
    external_id = str(entry.get("id") or entry.get("guid") or raw_link).strip()
    if not external_id:
        raise ValueError("RSS item has no stable identifier")
    if len(external_id) > 512:
        external_id = "sha256:" + hashlib.sha256(external_id.encode()).hexdigest()
    if raw_link:
        # Never store a scheme the reader could render as an active link
        # (javascript:, data:, ...). A bad link skips the item, not the feed.
        link = safe_http_url(raw_link)
        if link is None:
            raise InvalidEntryLink("RSS item link is not a valid http(s) URL")
    else:
        link = safe_http_url(
            f"{entry.get('_feed_url', '')}#{quote(external_id, safe='')}"
        )
        if link is None:
            raise InvalidEntryLink("RSS item has no usable link")
    title = _plain_text(entry.get("title", ""))[:500]
    content = entry.get("content") or []
    raw_body = content[0].get("value", "") if content else entry.get("summary", "")
    return external_id, link, title or link, _plain_text(raw_body), _published_at(entry)


def _apply_entry(
    source: Source, entry, fetched_at: datetime, *, backfill: bool = False
) -> None:
    # The entry identity is source-scoped. The database constraint also protects
    # retries and concurrent workers from creating duplicate observations.
    external_id, url, title, body, published_at = _entry_content(entry)
    fingerprint = hashlib.sha256(f"{title}\0{body}".encode()).hexdigest()
    try:
        with transaction.atomic():
            article = Article.objects.select_for_update().filter(
                source=source, external_id=external_id
            ).first()
            if article is None:
                article = Article.objects.select_for_update().filter(
                    source=source, url=url
                ).first()
            if article is None:
                article = Article.objects.select_for_update().filter(
                    source__isnull=True, url=url
                ).first()
            if article is None:
                article = Article.objects.create(
                    source=source,
                    external_id=external_id,
                    url=url,
                    title=title,
                    body=body,
                    source_published_at=published_at,
                    fetched_at=fetched_at,
                    # Observation-level intent: fixed by how the item was first seen,
                    # so replaying or finishing a backfill later never makes it "Today".
                    is_backfill=backfill,
                )
                ArticleRevision.objects.create(
                    article=article,
                    version=1,
                    title=title,
                    body=body,
                    content_hash=fingerprint,
                    source_published_at=published_at,
                    fetched_at=fetched_at,
                )
                return

            if article.source_id is None:
                # A manual submission of the same URL becomes the same article
                # (identity is URL-scoped), unless this source already owns a
                # row for that URL/GUID, in which case that row was matched above.
                # Its manual revision history is kept; the feed adds revisions.
                article.source = source
                article.external_id = external_id
                article.save(update_fields=["source", "external_id", "updated_at"])
            latest = article.revisions.order_by("-version").first()
            if latest and latest.content_hash == fingerprint:
                return
            version = (latest.version if latest else article.current_version) + 1
            ArticleRevision.objects.create(
                article=article,
                version=version,
                title=title,
                body=body,
                content_hash=fingerprint,
                source_published_at=published_at,
                fetched_at=fetched_at,
            )
            # Publication timestamp wins when both versions supply it; otherwise
            # use observation/fetch time. Older replays remain in history but do
            # not replace the current display snapshot.
            if published_at is not None and article.source_published_at is not None:
                is_newer = published_at >= article.source_published_at
            else:
                is_newer = article.fetched_at is None or fetched_at >= article.fetched_at
            if is_newer:
                article.title = title
                article.body = body
                article.current_version = version
                if published_at is not None:
                    # A feed that omits the date must not erase a known one.
                    article.source_published_at = published_at
                article.fetched_at = fetched_at
                article.save(update_fields=[
                    "title", "body", "current_version", "source_published_at",
                    "fetched_at", "updated_at",
                ])
    except IntegrityError:
        # A concurrent retry may have won the unique source/GUID or URL race.
        # Re-read it and accept only an equivalent stable identity.
        existing = Article.objects.filter(source=source, external_id=external_id).first()
        if existing is None:
            raise


def poll_rss_source(payload: dict) -> int:
    """Fetch one configured RSS source; persist observations quietly and idempotently."""
    source_id = payload.get("source_id")
    if not isinstance(source_id, int):
        raise TypeError("RSS job requires a source_id")
    try:
        source = Source.objects.get(pk=source_id)
    except Source.DoesNotExist as exc:
        raise ValueError("RSS source no longer exists") from exc

    attempted_at = timezone.now()
    try:
        if not source.rss_feed_url:
            raise ValueError("RSS source has no configured feed URL")
        raw_feed = _fetch_feed(source.rss_feed_url)
        parsed = feedparser.parse(raw_feed)
        if parsed.bozo and not parsed.entries:
            raise ValueError("Malformed RSS feed")
        backfill = payload.get("backfill") is True
        count = 0
        skipped = 0
        for entry in parsed.entries:
            # Feedparser entries are mappings; avoid modifying the parser-owned data.
            entry = dict(entry)
            entry["_feed_url"] = source.rss_feed_url
            try:
                _apply_entry(source, entry, attempted_at, backfill=backfill)
            except InvalidEntryLink:
                skipped += 1
                continue
            count += 1
        # Skipped items stay visible to the operator without failing the feed.
        note = f"Skipped {skipped} item(s) with missing or non-http(s) links" if skipped else ""
        Source.objects.filter(pk=source.pk).update(
            last_fetch_at=attempted_at, last_error=note, consecutive_failures=0
        )
        return count
    except Exception as exc:
        # Keep a compact operational error; no response body or credentials are stored.
        error = type(exc).__name__
        if isinstance(exc, ValueError):
            error = str(exc)[:300]
        Source.objects.filter(pk=source.pk).update(
            last_fetch_at=attempted_at,
            last_error=error,
            consecutive_failures=F("consecutive_failures") + 1,
        )
        raise
