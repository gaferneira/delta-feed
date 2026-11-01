import pytest

from delta_feed.analysis.contracts.extraction import EXTRACTION_SCHEMA_ID
from delta_feed.analysis.models import AnalysisRun
from delta_feed.content.models import Article

pytestmark = pytest.mark.django_db


class FakeExtractionAdapter:
    model_version = "fake-model-v1"

    def __init__(self, result):
        self.result = result
        self.prompt = None

    def analyze(self, prompt, output_schema):
        self.prompt = prompt
        return self.result


def test_extraction_pipeline_validates_output_and_records_analysis_provenance():
    from delta_feed.analysis.use_cases import extract_article

    article = Article.objects.create(
        url="https://example.org/extraction", title="Widget release", body="Widget supports ARM."
    )
    adapter = FakeExtractionAdapter(
        {
            "schema_id": EXTRACTION_SCHEMA_ID,
            "entities": [
                {
                    "ref": "widget",
                    "name": "Widget",
                    "entity_type": "software",
                    "evidence": [{"start": 0, "end": 6, "quote": "Widget"}],
                }
            ],
            "claims": [
                {
                    "entity_ref": "widget",
                    "predicate": "supports",
                    "value": "ARM",
                    "scope": {"version": None, "platform": None, "availability": None},
                    "confidence": 0.75,
                    "evidence": [{"start": 0, "end": 20, "quote": "Widget supports ARM."}],
                }
            ],
        }
    )

    run, result = extract_article(source_article=article, adapter=adapter)

    run.refresh_from_db()
    assert run.status == AnalysisRun.Status.COMPLETED
    assert run.model_version == "fake-model-v1"
    assert run.prompt_version == "delta-feed.extract-claims.v1"
    assert run.schema_version == EXTRACTION_SCHEMA_ID
    assert "Widget release" in adapter.prompt
    assert result.claims[0].scope.availability is None


def test_extraction_pipeline_marks_run_failed_when_output_is_invalid():
    from pydantic import ValidationError

    from delta_feed.analysis.use_cases import extract_article

    article = Article.objects.create(
        url="https://example.org/invalid-extraction", title="Bad output", body="Text"
    )
    adapter = FakeExtractionAdapter({"unexpected": True})

    with pytest.raises(ValidationError):
        extract_article(source_article=article, adapter=adapter)

    run = AnalysisRun.objects.get(source_article=article)
    assert run.status == AnalysisRun.Status.FAILED
    assert run.schema_version == EXTRACTION_SCHEMA_ID


def test_extraction_pipeline_rejects_evidence_not_found_in_article():
    from delta_feed.analysis.use_cases import extract_article

    article = Article.objects.create(
        url="https://example.org/fabricated-evidence", title="Widget release", body="Widget is stable."
    )
    adapter = FakeExtractionAdapter(
        {
            "schema_id": EXTRACTION_SCHEMA_ID,
            "entities": [
                {
                    "ref": "widget",
                    "name": "Widget",
                    "entity_type": "software",
                    "evidence": [{"start": 0, "end": 6, "quote": "Widget"}],
                }
            ],
            "claims": [
                {
                    "entity_ref": "widget",
                    "predicate": "availability",
                    "value": "generally available",
                    "scope": {"version": None, "platform": None, "availability": "stable"},
                    "confidence": 0.7,
                    "evidence": [
                        {"start": 10, "end": 16, "quote": "closed"}
                    ],
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="does not match"):
        extract_article(source_article=article, adapter=adapter)

    run = AnalysisRun.objects.get(source_article=article)
    assert run.status == AnalysisRun.Status.FAILED
