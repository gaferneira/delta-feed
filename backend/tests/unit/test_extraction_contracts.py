import pytest
from pydantic import ValidationError

from delta_feed.analysis.contracts.extraction import (
    EXTRACTION_SCHEMA_ID,
    ExtractionResult,
    resolve_evidence,
)


def valid_result():
    return {
        "schema_id": EXTRACTION_SCHEMA_ID,
        "entities": [
            {
                "ref": "entity-1",
                "name": "Widget",
                "entity_type": "software",
                "evidence": [{"quote": "Widget"}],
            }
        ],
        "claims": [
            {
                "entity_ref": "entity-1",
                "predicate": "supports",
                "value": "ARM64",
                "scope": {"version": "2.1", "platform": "Linux", "availability": "stable"},
                "confidence": 0.9,
                "evidence": [{"quote": "supports ARM64 on Linux"}],
            }
        ],
    }


def test_extraction_result_accepts_structured_claim_with_scope_and_evidence():
    result = ExtractionResult.model_validate(valid_result())

    assert result.schema_id == EXTRACTION_SCHEMA_ID
    assert result.claims[0].scope.platform == "Linux"


def test_evidence_offsets_are_resolved_from_verbatim_quotes():
    result = ExtractionResult.model_validate(valid_result())

    output = resolve_evidence(result, "Widget supports ARM64 on Linux")

    assert output["claims"][0]["evidence"] == [
        {"start": 7, "end": 30, "quote": "supports ARM64 on Linux"}
    ]


def test_evidence_quotes_must_match_supplied_source_text():
    result = ExtractionResult.model_validate(valid_result())

    output = resolve_evidence(result, "Widget supports ARM64 on Windows")

    assert [entity["ref"] for entity in output["entities"]] == ["entity-1"]
    assert output["claims"] == []
    assert output["dropped"] == [
        {"kind": "claim", "ref": "entity-1", "reason": "evidence_not_found", "detail": "supports"}
    ]


def test_output_is_rejected_when_no_item_survives():
    result = ExtractionResult.model_validate(valid_result())

    with pytest.raises(ValueError, match="no extracted item survived"):
        resolve_evidence(result, "Unrelated text")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(schema_id="extraction-v0"),
        lambda data: data["claims"][0].update(confidence=1.5),
        lambda data: data["claims"][0].update(unreviewed_field="bad"),
        lambda data: data["entities"][0].update(name=123),
        lambda data: data["claims"][0]["evidence"][0].update(start=7),
    ],
)
def test_extraction_result_rejects_malformed_or_unscoped_output(mutate):
    data = valid_result()
    mutate(data)

    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(data)
