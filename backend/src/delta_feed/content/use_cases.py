from django.db import transaction

from delta_feed.content.models import Source
from delta_feed.jobs.services import enqueue_job


def register_source(*, name: str, rss_feed_url: str, homepage_url: str = "") -> tuple[Source, int]:
    """Create a source and queue its one-time quiet backfill; returns (source, backfill job id)."""
    with transaction.atomic():
        source = Source.objects.create(
            name=name, rss_feed_url=rss_feed_url, homepage_url=homepage_url
        )
        job = enqueue_job(
            job_type="rss.poll",
            payload={"source_id": source.pk, "backfill": True},
            handler_name="content.poll_rss",
        )
    return source, job.pk


def ensure_source(*, name: str, rss_feed_url: str, homepage_url: str = "") -> tuple[Source, bool]:
    """Return the source already registered for this feed, or register it (with its backfill).

    The boolean is True only when this call created the source. An existing source is
    never renamed or backfilled again.
    """
    with transaction.atomic():
        existing = Source.objects.filter(rss_feed_url=rss_feed_url).order_by("id").first()
        if existing is not None:
            return existing, False
        source, _job_id = register_source(
            name=name, rss_feed_url=rss_feed_url, homepage_url=homepage_url
        )
        return source, True
