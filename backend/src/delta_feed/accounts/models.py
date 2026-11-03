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
