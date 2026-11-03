from datetime import datetime, timedelta

from django.db.models import Min
from django.http import HttpRequest
from django.utils import timezone
from ninja import Field, Router, Schema
from ninja.responses import Status
from pydantic import field_validator

from delta_feed.content.models import Source
from delta_feed.content.urls import safe_http_url
from delta_feed.content.use_cases import register_source
from delta_feed.jobs.models import Job

router = Router(tags=["content sources"])


class SourceSummary(Schema):
    id: int
    name: str
    rss_feed_url: str
    last_fetch_at: datetime | None
    last_error: str
    consecutive_failures: int


@router.get("/sources", response=list[SourceSummary])
def list_rss_sources(request: HttpRequest):
    return Source.objects.order_by("id")


class SourceRegistration(Schema):
    name: str = Field(min_length=1, max_length=200)
    rss_feed_url: str = Field(min_length=8, max_length=2048)
    homepage_url: str = Field(default="", max_length=2048)

    @field_validator("rss_feed_url", "homepage_url")
    @classmethod
    def validate_http_url(cls, value: str, info):
        if value == "" and info.field_name == "homepage_url":
            return value
        if safe_http_url(value) != value:
            raise ValueError("URL must be absolute HTTP(S) without credentials")
        return value


class SourceRegistrationResult(Schema):
    source_id: int
    backfill_job_id: int


@router.post("/sources", response={201: SourceRegistrationResult})
def register_rss_source(request: HttpRequest, payload: SourceRegistration):
    source, job_id = register_source(
        name=payload.name,
        rss_feed_url=payload.rss_feed_url,
        homepage_url=payload.homepage_url,
    )
    return Status(201, {"source_id": source.pk, "backfill_job_id": job_id})


WORKER_ACTIVITY_WINDOW = timedelta(minutes=5)


class ImportStatus(Schema):
    sources_total: int
    sources_fetched: int
    pending_jobs: int
    oldest_pending_seconds: int | None
    worker_seen_recently: bool


@router.get("/import-status", response=ImportStatus)
def import_status(request: HttpRequest):
    """Progress of source polling, for first-run and empty-Today messaging."""
    now = timezone.now()
    pending = Job.objects.filter(
        type="rss.poll", status__in=[Job.Status.PENDING, Job.Status.RUNNING]
    )
    oldest = pending.aggregate(oldest=Min("created_at"))["oldest"]
    # A worker leaves no heartbeat; recent job handling (claimed, retried, finished)
    # is the evidence it is running. A job nobody has touched since enqueue is not.
    worker_seen = (
        Job.objects.filter(updated_at__gte=now - WORKER_ACTIVITY_WINDOW)
        .exclude(status=Job.Status.PENDING, attempt_count=0)
        .exists()
    )
    return {
        "sources_total": Source.objects.exclude(rss_feed_url="").count(),
        "sources_fetched": Source.objects.exclude(rss_feed_url="").filter(
            last_fetch_at__isnull=False, consecutive_failures=0
        ).count(),
        "pending_jobs": pending.count(),
        "oldest_pending_seconds": int((now - oldest).total_seconds()) if oldest else None,
        "worker_seen_recently": worker_seen,
    }
