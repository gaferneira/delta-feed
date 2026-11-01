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
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ClaimQuerySet.as_manager()

    class Meta:
        ordering = ["-observed_at", "-id"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.CheckConstraint(
                condition=models.Q(evidence_end__gt=models.F("evidence_start")),
                name="claim_evidence_span_nonempty",
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
