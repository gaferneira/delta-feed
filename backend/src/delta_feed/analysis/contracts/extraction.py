"""Strict schema for entity and scoped-claim extraction proposals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EXTRACTION_SCHEMA_ID = "delta-feed.extraction.v1"


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceSpan(StrictContract):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def end_follows_start(self):
        if self.end <= self.start:
            raise ValueError("evidence end must be greater than start")
        return self


class EntityMention(StrictContract):
    ref: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=250)
    entity_type: str = Field(min_length=1, max_length=80)
    evidence: list[EvidenceSpan] = Field(min_length=1)


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
    evidence: list[EvidenceSpan] = Field(min_length=1)


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


def validate_evidence_spans(result: ExtractionResult, source_text: str) -> ExtractionResult:
    """Reject evidence whose offsets or exact quote do not match source text."""
    spans = [span for entity in result.entities for span in entity.evidence]
    spans.extend(span for claim in result.claims for span in claim.evidence)
    for span in spans:
        if span.end > len(source_text) or source_text[span.start : span.end] != span.quote:
            raise ValueError("evidence span does not match the supplied source text")
    return result
