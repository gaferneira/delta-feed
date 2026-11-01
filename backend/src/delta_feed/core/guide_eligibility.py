"""Deterministic matching of guide criteria against entity/source text."""

import re
from collections.abc import Iterable

_WORD_RE = re.compile(r"[\w+#.-]+", re.UNICODE)
_STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "works",
}


def find_eligibility_matches(
    criteria: Iterable[str], text_fields: Iterable[tuple[str, str]]
) -> list[tuple[str, str]]:
    """Return (criterion, field label) matches using literal keywords only.

    Each criterion is treated as an OR-list of its non-trivial words; a full
    normalized phrase also matches. This deliberately does no semantic or model
    judgment. Matches are reviewable signals, not recommendations.
    """
    fields = [
        (label, text.casefold(), set(_WORD_RE.findall(text.casefold())))
        for label, text in text_fields
        if text
    ]
    matches: list[tuple[str, str]] = []
    for criterion in criteria:
        if not isinstance(criterion, str) or not criterion.strip():
            continue
        normalized = criterion.casefold().strip()
        keywords = {
            token for token in _WORD_RE.findall(normalized) if token not in _STOP_WORDS
        }
        for label, field_text, tokens in fields:
            if normalized in field_text or keywords.intersection(tokens):
                matches.append((criterion, label))
                break
    return matches
