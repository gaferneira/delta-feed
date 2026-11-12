from django.db import models
from django.utils import timezone


class Entity(models.Model):
    """A globally known identity with exact strong identifiers and name aliases."""

    name = models.CharField(max_length=250)
    type = models.CharField(max_length=80)
    canonical_url = models.URLField(max_length=2048, null=True, blank=True, unique=True)
    slug = models.CharField(max_length=250, null=True, blank=True, unique=True)
    # Additional namespaced strong identifiers, e.g. {"repository": "org/name"}.
    identifiers = models.JSONField(default=dict)
    # Aliases are display/search terms, never strong identity keys.
    aliases = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]  # noqa: RUF012

    def __str__(self):
        return self.name


class Topic(models.Model):
    """Shared topic with a stable slug; sources attach to it, readers select it."""

    slug = models.SlugField(max_length=60, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    sources = models.ManyToManyField("content.Source", blank=True, related_name="topics")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]  # noqa: RUF012

    def __str__(self):
        return self.title


class EntityEmbedding(models.Model):
    """Versioned entity vector stored portably as a JSON list of floats."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="embeddings")
    model_version = models.CharField(max_length=120)
    vector = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["entity_id", "model_version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=("entity", "model_version"), name="unique_entity_embedding_model"
            ),
        ]

    def __str__(self):
        return f"Embedding for {self.entity_id} ({self.model_version})"


class ExtractedMention(models.Model):
    """An entity mention from an extraction run, waiting for or past resolution."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    analysis_run = models.ForeignKey(
        "analysis.AnalysisRun", on_delete=models.CASCADE, related_name="mentions"
    )
    source_article = models.ForeignKey(
        "content.Article", on_delete=models.CASCADE, related_name="mentions"
    )
    ref = models.CharField(max_length=80)
    name = models.CharField(max_length=250)
    normalized_name = models.CharField(max_length=250, db_index=True)
    entity_type = models.CharField(max_length=80)
    evidence = models.JSONField(default=list)
    claims = models.JSONField(default=list)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    entity = models.ForeignKey(
        Entity, null=True, blank=True, on_delete=models.PROTECT, related_name="mentions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    compared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=("analysis_run", "ref"), name="unique_mention_run_ref"
            ),
        ]

    def __str__(self):
        return f"Mention {self.name} ({self.status})"


class ClaimQuerySet(models.QuerySet):
    """Disallow bulk mutation paths that would rewrite append-only observations."""

    def update(self, **kwargs):
        raise ValueError("Claims are append-only; updates are not allowed")

    def delete(self):
        raise ValueError("Claims are append-only; deletion is not allowed")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError("Claims are append-only; updates are not allowed")


class Claim(models.Model):
    """Immutable, source-attributed assertion with structured scope and provenance."""

    class Classification(models.TextChoices):
        NEW = "new", "New"
        DUPLICATE = "duplicate", "Duplicate"
        REFINEMENT = "refinement", "Refinement"
        CONTRADICTION = "contradiction", "Contradiction"
        UNSURE = "unsure", "Unsure"

    class ComparisonMethod(models.TextChoices):
        FINGERPRINT = "fingerprint", "Fingerprint"
        LEXICAL = "lexical", "Lexical"
        MODEL = "model", "Model"
        FIRST_SIGHTING = "first_sighting", "First sighting"
        MANUAL = "manual", "Manual"

    entity = models.ForeignKey(Entity, on_delete=models.PROTECT, related_name="claims")
    version = models.CharField(max_length=120, null=True, blank=True)
    platform = models.CharField(max_length=120, null=True, blank=True)
    availability = models.CharField(max_length=120, null=True, blank=True)
    claim_text = models.TextField()
    source_article = models.ForeignKey(
        "content.Article", on_delete=models.PROTECT, related_name="claims"
    )
    evidence_start = models.PositiveIntegerField()
    evidence_end = models.PositiveIntegerField()
    evidence_text = models.TextField()
    observed_at = models.DateTimeField(default=timezone.now)
    analysis_run = models.ForeignKey(
        "analysis.AnalysisRun", on_delete=models.PROTECT, related_name="claims"
    )
    classification = models.CharField(max_length=20, choices=Classification.choices)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="superseded_by",
    )
    predicate = models.CharField(max_length=120, null=True, blank=True)
    value = models.TextField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64, null=True, blank=True, db_index=True)
    matched_claim = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="matched_by",
    )
    comparison_method = models.CharField(
        max_length=20,
        choices=ComparisonMethod.choices,
        default=ComparisonMethod.MANUAL,
    )
    comparison_model_version = models.CharField(max_length=120, blank=True)
    comparison_prompt_version = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ClaimQuerySet.as_manager()

    class Meta:
        ordering = ["-observed_at", "-id"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=models.Q(evidence_end__gt=models.F("evidence_start")),
                name="claim_evidence_span_nonempty",
            ),
            models.UniqueConstraint(
                fields=("analysis_run", "fingerprint"),
                condition=models.Q(fingerprint__isnull=False),
                name="unique_claim_run_fingerprint",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding or (self.pk is not None and type(self).objects.filter(pk=self.pk).exists()):
            raise ValueError("Claims are append-only; updates are not allowed")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Claims are append-only; deletion is not allowed")

    def __str__(self):
        return f"Claim {self.pk} for entity {self.entity_id}"
