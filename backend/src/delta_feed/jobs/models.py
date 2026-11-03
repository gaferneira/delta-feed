import uuid

from django.db import models
from django.utils import timezone


class Job(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    handler_name = models.CharField(max_length=100)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    run_after = models.DateTimeField(default=timezone.now)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    # Compact, non-sensitive outcome reported by the handler (e.g. skipped counts).
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["run_after", "created_at", "id"]  # noqa: RUF012
        indexes = [  # noqa: RUF012
            models.Index(fields=["status", "run_after"], name="jobs_due_idx"),
            models.Index(fields=["status", "lease_expires_at"], name="jobs_lease_idx"),
        ]

    def __str__(self):
        return f"{self.type}#{self.pk} ({self.status})"


def new_lease_token():
    return uuid.uuid4()
