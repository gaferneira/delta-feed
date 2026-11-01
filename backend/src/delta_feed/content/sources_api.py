from datetime import datetime

from django.db import transaction
from django.http import HttpRequest
from ninja import Field, Router, Schema
from ninja.responses import Status
from pydantic import field_validator

from delta_feed.content.models import Source
from delta_feed.content.urls import safe_http_url
from delta_feed.jobs.services import enqueue_job

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
    with transaction.atomic():
        source = Source.objects.create(
            name=payload.name,
            rss_feed_url=payload.rss_feed_url,
            homepage_url=payload.homepage_url,
        )
        job = enqueue_job(
            job_type="rss.poll",
            payload={"source_id": source.pk, "backfill": True},
            handler_name="content.poll_rss",
        )
    return Status(201, {"source_id": source.pk, "backfill_job_id": job.pk})
