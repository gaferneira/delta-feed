from django.db import models

DEFAULT_EXTRACTION_SCHEMA_ID = "delta-feed.extraction.v1"


class AnalysisRun(models.Model):
    """Provenance for one analysis attempt; no provider execution is owned here."""

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    source_article = models.ForeignKey(
        "content.Article",
        on_delete=models.CASCADE,
        related_name="analysis_runs",
    )
    # The exact immutable snapshot that was analysed; claim spans index into its body.
    # Nullable only for runs recorded before revisions were tracked.
    article_revision = models.ForeignKey(
        "content.ArticleRevision",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="analysis_runs",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    model_version = models.CharField(max_length=120)
    prompt_version = models.CharField(max_length=120)
    schema_version = models.CharField(
        max_length=100,
        default=DEFAULT_EXTRACTION_SCHEMA_ID,
    )

    class Meta:
        ordering = ["-started_at", "-id"]  # noqa: RUF012

    def __str__(self):
        return f"Analysis run {self.pk} ({self.status})"
