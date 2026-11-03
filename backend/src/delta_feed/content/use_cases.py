from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from delta_feed.content.models import Source
from delta_feed.jobs.models import Job
from delta_feed.jobs.services import enqueue_job

MAX_POLL_BACKOFF = timedelta(hours=24)


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


def poll_delay(consecutive_failures: int, interval: timedelta) -> timedelta:
    """Time to wait after the last fetch attempt: interval x 2^failures, capped at 24 hours."""
    return min(interval * (2 ** min(consecutive_failures, 16)), MAX_POLL_BACKOFF)


def schedule_due_polls(now: datetime | None = None) -> list[int]:
    """Enqueue one rss.poll job per source whose next poll is due; returns the source ids.

    A source with a pending or leased rss.poll job is never given a second one. A source
    that never completed its bounded initial import gets a backfill poll again instead
    of a recurring one, so recurring polls always run against a stored backfill cutoff.
    """
    now = now or timezone.now()
    interval = timedelta(minutes=settings.RSS_POLL_INTERVAL_MINUTES)
    active = {
        job.payload.get("source_id")
        for job in Job.objects.filter(
            type="rss.poll", status__in=[Job.Status.PENDING, Job.Status.RUNNING]
        )
    }
    scheduled = []
    for source in Source.objects.exclude(rss_feed_url="").order_by("id"):
        if source.pk in active:
            continue
        if source.last_fetch_at is not None and now < source.last_fetch_at + poll_delay(
            source.consecutive_failures, interval
        ):
            continue
        enqueue_job(
            job_type="rss.poll",
            payload={"source_id": source.pk, "backfill": source.backfill_cutoff is None},
            handler_name="content.poll_rss",
        )
        scheduled.append(source.pk)
    return scheduled
