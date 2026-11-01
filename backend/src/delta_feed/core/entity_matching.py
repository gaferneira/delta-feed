import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

EntityKey = TypeVar("EntityKey")


@dataclass(frozen=True)
class RankedCandidate:
    entity_key: object
    similarity: float


def match_exact_identifiers(  # noqa: UP047 - keep compatibility with Python 3.11 tooling
    candidate_identifiers: Mapping[str, str],
    known_entities: Iterable[tuple[EntityKey, Mapping[str, str]]],
) -> EntityKey | None:
    """Return the sole entity sharing an exact strong identifier, else ``None``.

    Identifier type and value are both compared exactly. Empty candidate sets,
    fuzzy similarity, and ambiguous matches never produce an entity result.
    """
    candidates = {
        (kind, value)
        for kind, value in candidate_identifiers.items()
        if kind and value
    }
    if not candidates:
        return None

    matched_keys = {
        entity_key
        for entity_key, identifiers in known_entities
        if any((kind, value) in candidates for kind, value in identifiers.items())
    }
    if len(matched_keys) != 1:
        return None
    return next(iter(matched_keys))


def rank_embedding_candidates(  # noqa: UP047 - keep compatibility with Python 3.11 tooling
    query_vector: Sequence[float],
    known_entities: Iterable[tuple[EntityKey, Sequence[float]]],
    *,
    limit: int | None = None,
) -> list[RankedCandidate]:
    """Rank compatible vectors by cosine similarity, without making a match decision.

    Invalid stored vectors and dimension mismatches are skipped. The query vector
    must be finite, non-empty, and non-zero. Callers must treat results as review
    candidates, never as silent merges or suppression decisions.
    """
    query = tuple(float(value) for value in query_vector)
    if not query or any(not math.isfinite(value) for value in query):
        raise ValueError("query vector must be non-empty and finite")
    query_norm = math.sqrt(sum(value * value for value in query))
    if query_norm == 0:
        raise ValueError("query vector must not be zero")

    ranked: list[RankedCandidate] = []
    for entity_key, raw_vector in known_entities:
        try:
            vector = tuple(float(value) for value in raw_vector)
        except (TypeError, ValueError):
            continue
        if len(vector) != len(query) or any(not math.isfinite(value) for value in vector):
            continue
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            continue
        similarity = sum(left * right for left, right in zip(query, vector, strict=True)) / (
            query_norm * norm
        )
        ranked.append(RankedCandidate(entity_key, max(-1.0, min(1.0, similarity))))

    ranked.sort(key=lambda candidate: (-candidate.similarity, str(candidate.entity_key)))
    return ranked if limit is None else ranked[:limit]
