"""Deterministic claim normalization and fingerprints; no Django dependency."""

import hashlib
from collections.abc import Mapping
from typing import Any

from delta_feed.core.claim_delta import SCOPE_FIELDS

_TRAILING_PUNCTUATION = ".,;:!?"


def normalize_text(text: str) -> str:
    """Lowercase, collapse whitespace and strip trailing punctuation."""
    collapsed = " ".join(str(text).casefold().split())
    return collapsed.rstrip(_TRAILING_PUNCTUATION).rstrip()


def normalize_name(name: str) -> str:
    """Normalize entity names, aliases and mention names for comparison."""
    return normalize_text(name)


def claim_fingerprint(
    entity_id: int, predicate: str, value: str, scope: Mapping[str, Any]
) -> str:
    """sha256 over entity, normalized predicate/value and scope, `|`-joined."""
    parts = [
        str(entity_id),
        normalize_text(predicate),
        normalize_text(value),
        *(str(scope.get(field) or "") for field in SCOPE_FIELDS),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
