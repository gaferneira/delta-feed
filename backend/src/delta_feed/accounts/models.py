from django.conf import settings
from django.db import models


class SetupToken(models.Model):
    """One-time token that gates first-run account creation.

    Only the SHA-256 hash is stored; the plaintext is shown once in the server logs
    (or by ``manage.py setup_token``). ``slot`` is always 1 and unique, so the database
    itself guarantees at most one token exists, even when requests race to issue one.
    """

    slot = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    token_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class ReaderProfile(models.Model):
    """Per-user reader state. A missing profile means onboarding is not complete."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reader_profile"
    )
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)


class TopicSelection(models.Model):
    """A topic the user picked during onboarding; selection is personal, topics are shared."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="topic_selections"
    )
    topic = models.ForeignKey(
        "knowledge.Topic", on_delete=models.CASCADE, related_name="selections"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [  # noqa: RUF012
            models.UniqueConstraint(fields=["user", "topic"], name="unique_user_topic_selection"),
        ]
