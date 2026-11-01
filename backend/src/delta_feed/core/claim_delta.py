"""Deterministic, conservative claim-delta classification; no Django dependency."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

SCOPE_FIELDS = ("version", "platform", "availability")
_NEGATION = {"not", "no", "never", "without", "cannot", "can't", "isn't", "aren't", "doesn't", "don't"}
_AUXILIARIES = {"do", "does", "did", "is", "are", "was", "were", "will", "can"}
_TOKEN = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?", re.IGNORECASE)


def _get(claim: Mapping[str, Any] | Any, key: str, default=None):
    if isinstance(claim, Mapping):
        return claim.get(key, default)
    return getattr(claim, key, default)


def _scope(claim: Mapping[str, Any] | Any) -> tuple[Any, ...]:
    return tuple(_get(claim, field) for field in SCOPE_FIELDS)


def _assertion(claim: Mapping[str, Any] | Any) -> tuple[bool, frozenset[str], str]:
    text = " ".join(str(_get(claim, "claim_text", "")).casefold().split())
    tokens = [token.casefold().replace("’", "'") for token in _TOKEN.findall(text)]
    negated = any(token in _NEGATION for token in tokens)
    canonical = []
    for token in tokens:
        if token in _NEGATION or token in _AUXILIARIES:
            continue
        # A small deterministic inflection rule makes "supports" and "support"
        # comparable without stemming or semantic inference.
        if len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        canonical.append(token)
    return negated, frozenset(canonical), " ".join(tokens)


def classify_claim_delta(
    new_claim: Mapping[str, Any] | Any,
    existing_claims: Sequence[Mapping[str, Any] | Any],
) -> str:
    """Return duplicate/refinement/contradiction/new using scope and text rules.

    This intentionally does not infer semantic equivalence. Only normalized
    exact assertions, explicit lexical negation, and strict token-set detail
    additions are recognized. Unclear/unrelated assertions remain ``new`` and
    are therefore reviewable rather than being silently suppressed.
    """
    new_negated, new_tokens, new_text = _assertion(new_claim)
    comparable = [claim for claim in existing_claims if _scope(claim) == _scope(new_claim)]
    if not comparable:
        return "new"

    assertions = [_assertion(claim) for claim in comparable]
    if any(old_text == new_text for _, _, old_text in assertions):
        return "duplicate"
    if any(old_tokens == new_tokens and old_negated != new_negated for old_negated, old_tokens, _ in assertions):
        return "contradiction"
    if any(old_tokens < new_tokens and old_negated == new_negated for old_negated, old_tokens, _ in assertions):
        return "refinement"
    return "new"
