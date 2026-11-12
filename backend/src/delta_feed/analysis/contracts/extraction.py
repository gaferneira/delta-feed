"""Strict schema for entity and scoped-claim extraction proposals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EXTRACTION_SCHEMA_ID = "delta-feed.extraction.v1"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceQuote(StrictContract):
    """A passage copied verbatim from the article; offsets are resolved server-side."""

    quote: str = Field(min_length=1)


# Coarse on purpose: a mention resolves to an entity only when name and type both
# match, so fine-grained types ("LLM", "Software Version") would split one thing.
EntityType = Literal["software", "hardware", "model", "service", "practice", "other"]


class EntityMention(StrictContract):
    ref: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    entity_type: EntityType
    evidence: list[EvidenceQuote] = Field(min_length=1)


class ClaimScope(StrictContract):
    version: str | None = None
    platform: str | None = None
    availability: str | None = None


class ExtractedClaim(StrictContract):
    entity_ref: str = Field(min_length=1, max_length=80)
    predicate: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1)
    scope: ClaimScope
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceQuote] = Field(min_length=1)


class ExtractionResult(StrictContract):
    schema_id: Literal["delta-feed.extraction.v1"]
    entities: list[EntityMention]
    claims: list[ExtractedClaim]


def _resolve_quotes(item: dict, source_text: str) -> None:
    """Keep only the quotes found verbatim in source_text, with their offsets."""
    spans = []
    for evidence in item["evidence"]:
        quote = evidence["quote"]
        start = source_text.find(quote)
        if start >= 0:
            spans.append({"start": start, "end": start + len(quote), "quote": quote})
    item["evidence"] = spans


def resolve_evidence(result: ExtractionResult, source_text: str) -> dict:
    """Return the result as JSON data with each quote's offsets into source_text.

    Models count characters unreliably, so they supply exact quotes only and the
    offsets are computed here. Defective items (repeated or undeclared refs, quotes
    that are not verbatim) are dropped and listed under "dropped" instead of failing
    the whole article; if nothing at all survives, the output is rejected. An entity
    whose own quotes fail is kept when one of its claims has valid evidence, and
    borrows that claim's first span.
    """
    data = result.model_dump(mode="json")
    dropped: list[dict] = []
    entities: dict[str, dict] = {}
    for entity in data["entities"]:
        ref = entity["ref"]
        if ref in entities:
            dropped.append(_drop("entity", ref, "duplicate_ref", entity["name"]))
            continue
        _resolve_quotes(entity, source_text)
        entities[ref] = entity

    kept_claims = []
    for claim in data["claims"]:
        ref = claim["entity_ref"]
        _resolve_quotes(claim, source_text)
        if not claim["evidence"]:
            dropped.append(_drop("claim", ref, "evidence_not_found", claim["predicate"]))
        elif ref not in entities:
            dropped.append(_drop("claim", ref, "undeclared_entity", claim["predicate"]))
        else:
            kept_claims.append(claim)
            if not entities[ref]["evidence"]:
                entities[ref]["evidence"] = [dict(claim["evidence"][0])]

    kept_entities = []
    for ref, entity in entities.items():
        if entity["evidence"]:
            kept_entities.append(entity)
        else:
            dropped.append(_drop("entity", ref, "evidence_not_found", entity["name"]))

    if (data["entities"] or data["claims"]) and not kept_entities and not kept_claims:
        raise ValueError("no extracted item survived validation")
    data["entities"] = kept_entities
    data["claims"] = kept_claims
    data["dropped"] = dropped
    return data


def _drop(kind: str, ref: str, reason: str, detail: str) -> dict:
    return {"kind": kind, "ref": ref, "reason": reason, "detail": detail}
