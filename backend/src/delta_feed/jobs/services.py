from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from delta_feed.jobs.models import Job, new_lease_token

MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 30
MAX_BACKOFF_SECONDS = 3600
LEASE_SECONDS = 60
HANDLERS = {"content.poll_rss": "delta_feed.content.rss:poll_rss_source"}
JOB_TYPES = {"rss.poll": "content.poll_rss"}


def enqueue_job(*, job_type: str, payload: dict, handler_name: str) -> Job:
    if handler_name not in HANDLERS or JOB_TYPES.get(job_type) != handler_name:
        raise ValueError(f"Job handler/type is not allowlisted: {job_type}")
    if not job_type or len(job_type) > 100:
        raise ValueError("Invalid job type")
    return Job.objects.create(
        type=job_type,
        payload=payload,
        handler_name=handler_name,
        run_after=timezone.now(),
    )


def _get_handler(handler_name):
    if handler_name not in HANDLERS:
        raise ValueError(f"Job handler is not allowlisted: {handler_name}")
    handler = HANDLERS[handler_name]
    if callable(handler):
        return handler
    module_path, function_name = handler.split(":", 1)
    from importlib import import_module

    return getattr(import_module(module_path), function_name)


def claim_job(*, job_id=None) -> Job | None:
    """Atomically lease one due job; expired running leases are recoverable."""
    now = timezone.now()
    eligible = Q(status=Job.Status.PENDING, run_after__lte=now) | Q(
        status=Job.Status.RUNNING, lease_expires_at__lte=now
    )
    with transaction.atomic():
        Job.objects.filter(
            status=Job.Status.RUNNING,
            lease_expires_at__lte=now,
            attempt_count__gte=MAX_ATTEMPTS,
        ).update(
            status=Job.Status.FAILED,
            lease_expires_at=None,
            lease_token=None,
            last_error="Lease expired after maximum attempts",
            updated_at=now,
        )
        query = Job.objects.filter(eligible).order_by("run_after", "created_at", "id")
        if job_id is not None:
            query = query.filter(pk=job_id)
        query = query.select_for_update(skip_locked=True)
        job = query.first()
        if job is None:
            return None
        token = new_lease_token()
        changed = Job.objects.filter(pk=job.pk).filter(eligible).update(
            status=Job.Status.RUNNING,
            lease_expires_at=now + timedelta(seconds=LEASE_SECONDS),
            lease_token=token,
            attempt_count=F("attempt_count") + 1,
            updated_at=now,
        )
        if not changed:
            return None
        job.refresh_from_db()
        return job


def _mark_failed(job: Job, error: Exception) -> None:
    now = timezone.now()
    retry = job.attempt_count < MAX_ATTEMPTS
    delay = min(BASE_BACKOFF_SECONDS * (2 ** max(0, job.attempt_count - 1)), MAX_BACKOFF_SECONDS)
    Job.objects.filter(
        pk=job.pk, status=Job.Status.RUNNING, lease_token=job.lease_token
    ).update(
        status=Job.Status.PENDING if retry else Job.Status.FAILED,
        run_after=now + timedelta(seconds=delay) if retry else now,
        lease_expires_at=None,
        lease_token=None,
        last_error=str(error)[:2000],
        updated_at=now,
    )


def execute_claimed_job(job: Job) -> bool:
    try:
        _get_handler(job.handler_name)(job.payload)
    except Exception as error:  # noqa: BLE001 - persist any handler failure for durable retry
        _mark_failed(job, error)
        return False
    return bool(
        Job.objects.filter(
            pk=job.pk, status=Job.Status.RUNNING, lease_token=job.lease_token
        ).update(
            status=Job.Status.SUCCEEDED,
            lease_expires_at=None,
            lease_token=None,
            last_error="",
            updated_at=timezone.now(),
        )
    )


def run_job(job_id: int) -> bool:
    job = claim_job(job_id=job_id)
    if job is None:
        return False
    return execute_claimed_job(job)
