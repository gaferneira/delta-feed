from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from delta_feed.adapters.knowledge import (
    find_entities_by_strong_identifiers,
    strong_identifiers_for,
)
from delta_feed.core.entity_matching import (
    match_exact_identifiers,
    rank_embedding_candidates,
)
from delta_feed.knowledge.models import Entity, EntityEmbedding


@dataclass(frozen=True)
class EntityCandidate:
    entity: Entity
    similarity: float


def match_entity_by_identifiers(
    candidate_identifiers: Mapping[str, str],
) -> Entity | None:
    """Resolve only a single exact strong-identifier match; no fuzzy lookup."""
    if not any(kind and value for kind, value in candidate_identifiers.items()):
        return None

    candidates = find_entities_by_strong_identifiers(candidate_identifiers)
    entity_id = match_exact_identifiers(
        candidate_identifiers,
        ((entity.pk, strong_identifiers_for(entity)) for entity in candidates),
    )
    if entity_id is None:
        return None
    return next(entity for entity in candidates if entity.pk == entity_id)


def match_or_suggest_entities(
    candidate_identifiers: Mapping[str, str],
    *,
    embedding: Sequence[float] | None = None,
    model_version: str | None = None,
    limit: int = 10,
) -> tuple[Entity | None, list[EntityCandidate]]:
    """Try exact identifiers first; otherwise return ranked review candidates.

    Similarity never merges entities or suppresses content. The caller must
    present returned candidates for human or bounded adjudication.
    """
    exact_match = match_entity_by_identifiers(candidate_identifiers)
    if exact_match is not None:
        return exact_match, []
    if embedding is None or not model_version:
        return None, []

    stored_embeddings = list(
        EntityEmbedding.objects.select_related("entity").filter(model_version=model_version)
    )
    ranked = rank_embedding_candidates(
        embedding,
        ((item.entity_id, item.vector) for item in stored_embeddings),
        limit=limit,
    )
    entities_by_id = {item.entity_id: item.entity for item in stored_embeddings}
    return None, [
        EntityCandidate(entities_by_id[item.entity_key], item.similarity)
        for item in ranked
        if item.entity_key in entities_by_id
    ]
