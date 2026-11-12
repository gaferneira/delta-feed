"""Strict schema for comparing new claims with an entity's baseline claims."""

from collections.abc import Collection
from typing import Literal

from pydantic import Field, model_validator

from delta_feed.analysis.contracts.extraction import StrictContract

COMPARISON_SCHEMA_ID = "delta-feed.comparison.v1"

Classification = Literal["duplicate", "refinement", "contradiction", "new", "unsure"]
_NEEDS_MATCH = {"duplicate", "refinement", "contradiction"}


class ComparisonResult(StrictContract):
    claim_index: int = Field(ge=0)
    classification: Classification
    matched_claim_id: int | None
    reason: str = Field(max_length=300)

    @model_validator(mode="after")
    def matched_id_must_fit_classification(self):
        needs_match = self.classification in _NEEDS_MATCH
        if needs_match and self.matched_claim_id is None:
            raise ValueError(f"{self.classification} requires a matched_claim_id")
        if not needs_match and self.matched_claim_id is not None:
            raise ValueError(f"{self.classification} must not have a matched_claim_id")
        return self


class ComparisonOutput(StrictContract):
    schema_id: Literal["delta-feed.comparison.v1"]
    results: list[ComparisonResult]


def single_results(
    output: ComparisonOutput, claim_count: int
) -> dict[int, ComparisonResult]:
    """Results by claim index, keeping only indexes in range that were answered once.

    Needs the claim count, which the provider adapters do not know, so it runs in
    code after model validation. Small models skip or repeat a claim now and then;
    those claims are left out here and recorded as unsure by the caller.
    """
    counts: dict[int, int] = {}
    for result in output.results:
        counts[result.claim_index] = counts.get(result.claim_index, 0) + 1
    return {
        result.claim_index: result
        for result in output.results
        if result.claim_index < claim_count and counts[result.claim_index] == 1
    }


def unknown_baseline_ids(
    output: ComparisonOutput, baseline_ids: Collection[int]
) -> set[int]:
    """Claim indexes whose matched id was not in the baseline supplied in the prompt."""
    known = set(baseline_ids)
    return {
        result.claim_index
        for result in output.results
        if result.matched_claim_id is not None and result.matched_claim_id not in known
    }
