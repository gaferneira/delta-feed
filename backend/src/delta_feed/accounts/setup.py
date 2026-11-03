"""First-run account setup: one-time token issuance and verification."""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from delta_feed.accounts.models import SetupToken

logger = logging.getLogger(__name__)

SETUP_TOKEN_TTL = timedelta(hours=24)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_matches(stored: SetupToken, candidate: str) -> bool:
    return hmac.compare_digest(stored.token_hash, hash_token(candidate))


def needs_setup() -> bool:
    return not get_user_model().objects.exists()


def _issue_locked() -> tuple[str, SetupToken]:
    plaintext = secrets.token_urlsafe(32)
    now = timezone.now()
    row = SetupToken.objects.create(token_hash=hash_token(plaintext), expires_at=now + SETUP_TOKEN_TTL)
    return plaintext, row


def ensure_setup_token() -> bool:
    """Issue and log a token when none is valid. Returns True only if this call issued one.

    Safe under concurrent callers: the row is locked (PostgreSQL) and ``slot`` is unique,
    so a lost race raises IntegrityError and issues nothing.
    """
    if not needs_setup():
        return False
    try:
        with transaction.atomic():
            existing = SetupToken.objects.select_for_update().filter(slot=1).first()
            if existing is not None:
                if existing.expires_at > timezone.now():
                    return False
                existing.delete()
            plaintext, row = _issue_locked()
    except IntegrityError:
        return False
    logger.warning(
        "Delta Feed setup token: %s (expires %s). Use it at /setup to create the first account.",
        plaintext,
        row.expires_at.isoformat(),
    )
    return True


def rotate_setup_token() -> tuple[str, SetupToken]:
    """Invalidate any existing token and issue a new one. Caller checks ``needs_setup``."""
    with transaction.atomic():
        SetupToken.objects.all().delete()
        return _issue_locked()
