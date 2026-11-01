from django.conf import settings
from django.db import models


class GuideDefinition(models.Model):
    """A personally curated guide and its editorial structure."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="guide_definitions",
    )
    title = models.CharField(max_length=250)
    purpose = models.TextField()
    audience = models.TextField()
    # Topic identities are represented as links until the knowledge app exists.
    topic_links = models.JSONField(default=list)
    eligibility_criteria = models.JSONField(default=list)
    # JSON arrays preserve section order; each section is a structured object.
    sections = models.JSONField(default=list)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]  # noqa: RUF012

    def __str__(self):
        return self.title


class GuideEntry(models.Model):
    """A structured guide recommendation plus separately preserved personal prose."""

    guide = models.ForeignKey(
        GuideDefinition,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    # Optional for entries created before entity links existed or imported prose.
    entity = models.ForeignKey(
        "knowledge.Entity",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="guide_entries",
    )
    entity_name = models.CharField(max_length=250)
    suitability = models.TextField(blank=True)
    requirements = models.JSONField(default=list)
    caveats = models.JSONField(default=list)
    evidence = models.JSONField(default=list)
    review_metadata = models.JSONField(default=dict)
    personal_prose = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)
    is_retired = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]  # noqa: RUF012

    def __str__(self):
        return self.entity_name


class GuideProposal(models.Model):
    """An evidence-backed guide change that remains pending until reviewed."""

    class ProposalType(models.TextChoices):
        ADD = "add", "Add entry"
        UPDATE = "update", "Update entry"
        WARNING = "warning", "Warning"
        RETIRE = "retire", "Retire entry"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    guide = models.ForeignKey(
        GuideDefinition,
        on_delete=models.CASCADE,
        related_name="proposals",
    )
    entity = models.ForeignKey(
        "knowledge.Entity",
        on_delete=models.CASCADE,
        related_name="guide_proposals",
    )
    analysis_run = models.ForeignKey(
        "analysis.AnalysisRun",
        on_delete=models.CASCADE,
        related_name="guide_proposals",
    )
    source_article = models.ForeignKey(
        "content.Article",
        on_delete=models.CASCADE,
        related_name="guide_proposals",
    )
    proposal_type = models.CharField(
        max_length=20,
        choices=ProposalType.choices,
        default=ProposalType.ADD,
    )
    target_entry = models.ForeignKey(
        "guides.GuideEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="target_proposals",
    )
    expected_revision = models.PositiveIntegerField(null=True, blank=True)
    proposed_entry = models.JSONField(default=dict)
    evidence = models.JSONField(default=list)
    reasoning = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    accepted_entry = models.OneToOneField(
        "guides.GuideEntry",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="accepted_proposal",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            # Add proposals have no target entry; update/warning/retire proposals are
            # unique per target entry so several entries for one entity in a guide
            # each get their own proposal instead of colliding.
            models.UniqueConstraint(
                fields=["guide", "entity", "analysis_run", "proposal_type"],
                condition=models.Q(target_entry__isnull=True),
                name="unique_guide_entity_analysis_untargeted_proposal",
            ),
            models.UniqueConstraint(
                fields=["guide", "entity", "analysis_run", "proposal_type", "target_entry"],
                condition=models.Q(target_entry__isnull=False),
                name="unique_guide_entity_analysis_targeted_proposal",
            ),
        ]

    def __str__(self):
        return f"Proposal to add {self.entity} to {self.guide} ({self.status})"


class GuideRevision(models.Model):
    """An append-only snapshot of a guide entry at one revision number."""

    entry = models.ForeignKey(
        GuideEntry,
        on_delete=models.CASCADE,
        related_name="revisions",
    )
    version = models.PositiveIntegerField()
    snapshot = models.JSONField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="guide_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["entry_id", "version"]  # noqa: RUF012
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(
                fields=["entry", "version"], name="unique_guide_entry_revision"
            ),
        ]

    def __str__(self):
        return f"{self.entry_id}@{self.version}"
