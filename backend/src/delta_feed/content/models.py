from django.conf import settings
from django.db import models


class Source(models.Model):
    """An explicitly configured publisher/source; submissions do not create one."""

    name = models.CharField(max_length=200, unique=True)
    homepage_url = models.URLField(max_length=2048, blank=True)
    rss_feed_url = models.URLField(max_length=2048, blank=True)
    last_fetch_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Article(models.Model):
    """Stable article identity with a pointer-like current snapshot."""

    source = models.ForeignKey(
        Source,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articles",
    )
    url = models.URLField(max_length=2048)
    external_id = models.CharField(max_length=512, null=True, blank=True)
    source_published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    title = models.CharField(max_length=500)
    body = models.TextField()
    current_version = models.PositiveIntegerField(default=1)
    # Quiet backfill: first observed as historical import; kept out of Today.
    is_backfill = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["url"],
                condition=models.Q(source__isnull=True),
                name="unique_manual_article_url",
            ),
            models.UniqueConstraint(
                fields=["source", "url"],
                condition=models.Q(source__isnull=False),
                name="unique_source_article_url",
            ),
            models.UniqueConstraint(
                fields=["source", "external_id"],
                condition=models.Q(source__isnull=False, external_id__isnull=False),
                name="unique_source_external_item",
            ),
        ]

    def __str__(self):
        return self.title


class ArticleRevision(models.Model):
    """Append-only submitted title/body snapshots for an article."""

    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    version = models.PositiveIntegerField()
    title = models.CharField(max_length=500)
    body = models.TextField()
    content_hash = models.CharField(max_length=64)
    source_published_at = models.DateTimeField(null=True, blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="article_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["article_id", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["article", "version"], name="unique_article_revision_version"
            ),
        ]

    def __str__(self):
        return f"{self.article_id}@{self.version}"
