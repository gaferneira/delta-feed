"""Strict schema for entity and scoped-claim extraction proposals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EXTRACTION_SCHEMA_ID = "delta-feed.extraction.v1"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceQuote(StrictContract):
    """A passage copied verbatim from the article; offsets are resolved server-side."""

    quote: str = Field(min_length=1)


class EntityMention(StrictContract):
    ref: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    entity_type: str = Field(min_length=1, max_length=80)
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

    @model_validator(mode="after")
    def claim_entities_must_be_declared(self):
        refs = [entity.ref for entity in self.entities]
        if len(set(refs)) != len(refs):
            raise ValueError("entity mention refs must be unique")
        declared = set(refs)
        if any(claim.entity_ref not in declared for claim in self.claims):
            raise ValueError("every claim must reference a declared entity mention")
        return self


def resolve_evidence(result: ExtractionResult, source_text: str) -> dict:
    """Return the result as JSON data with each quote's offsets into source_text.

    Models count characters unreliably, so they supply exact quotes only and the
    offsets are computed here. A quote that is not verbatim in the text is rejected.
    """
    data = result.model_dump(mode="json")
    for item in [*data["entities"], *data["claims"]]:
        spans = []
        for evidence in item["evidence"]:
            quote = evidence["quote"]
            start = source_text.find(quote)
            if start < 0:
                raise ValueError("evidence quote does not match the supplied source text")
            spans.append({"start": start, "end": start + len(quote), "quote": quote})
        item["evidence"] = spans
    return data
