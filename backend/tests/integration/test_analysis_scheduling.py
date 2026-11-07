from unittest.mock import patch

import pytest

from delta_feed.analysis.contracts.extraction import EXTRACTION_SCHEMA_ID
from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.providers import InferenceUnavailableError
from delta_feed.analysis.use_cases import (
    extract_article_job,
    schedule_due_analysis,
    unanalysed_articles,
)
from delta_feed.content.models import Article
from delta_feed.jobs.models import Job

pytestmark = pytest.mark.django_db


class FakeModel:
    model_version = "fake"

    def __init__(self, *, configured=True, output=None, error=None):
        self.configured = configured
        self.output = output
        self.error = error

    def is_configured(self):
        return self.configured

    def analyze(self, prompt, output_schema):
        if self.error:
            raise self.error
        return self.output


def use_model(model):
    return patch("delta_feed.analysis.use_cases.configured_language_model", return_value=model)


def article(slug, *, backfill=False):
    return Article.objects.create(
        url=f"https://example.org/{slug}", title=slug, body="Widget is stable.", is_backfill=backfill
    )


def test_nothing_is_queued_while_the_provider_is_unconfigured():
    article("a")
    with use_model(FakeModel(configured=False)):
        assert schedule_due_analysis() == []
    assert not Job.objects.exists()


def test_current_articles_are_queued_before_backfill_within_the_daily_budget(settings):
    settings.ANALYSIS_DAILY_BUDGET = 2
    old_backfill = article("backfill", backfill=True)
    older = article("older")
    newer = article("newer")

    with use_model(FakeModel()):
        assert schedule_due_analysis() == [newer.pk, older.pk]
        # A batch in flight blocks the next one, so priorities stay fresh.
        assert schedule_due_analysis() == []
    assert old_backfill.pk not in [job.payload["article_id"] for job in Job.objects.all()]


def test_invalid_output_settles_the_article_but_an_outage_leaves_it_unanalysed():
    broken = article("broken")
    offline = article("offline")

    with use_model(FakeModel(output={"schema_id": EXTRACTION_SCHEMA_ID, "unexpected": 1})):
        assert extract_article_job({"article_id": broken.pk}) == {"status": "invalid_output"}
    with use_model(FakeModel(error=InferenceUnavailableError("down"))), pytest.raises(
        InferenceUnavailableError
    ):
        extract_article_job({"article_id": offline.pk})

    assert AnalysisRun.objects.get(source_article=broken).failure_reason == "invalid_output"
    assert list(unanalysed_articles()) == [offline]
