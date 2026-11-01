from django.utils import timezone

from delta_feed.analysis.adapters.ollama import OllamaLanguageModel
from delta_feed.analysis.contracts.extraction import (
    ExtractionResult,
    validate_evidence_spans,
)
from delta_feed.analysis.models import DEFAULT_EXTRACTION_SCHEMA_ID, AnalysisRun
from delta_feed.analysis.prompts.extraction import (
    PROMPT_VERSION,
    render_extraction_prompt,
)
from delta_feed.content.models import Article, ArticleRevision
from delta_feed.content.revisions import current_revision


def record_run(
    *,
    source_article: Article,
    article_revision: ArticleRevision | None = None,
    status: str = AnalysisRun.Status.RUNNING,
    model_version: str,
    prompt_version: str,
    schema_version: str = DEFAULT_EXTRACTION_SCHEMA_ID,
    completed_at=None,
) -> AnalysisRun:
    """Persist analysis provenance; provider execution is owned by a separate use case."""
    if status != AnalysisRun.Status.RUNNING and completed_at is None:
        completed_at = timezone.now()
    article_revision = article_revision or current_revision(source_article)
    if article_revision.article_id != source_article.pk:
        raise ValueError("article_revision does not belong to source_article")
    return AnalysisRun.objects.create(
        source_article=source_article,
        article_revision=article_revision,
        status=status,
        model_version=model_version,
        prompt_version=prompt_version,
        schema_version=schema_version,
        completed_at=completed_at,
    )


def extract_article(
    *,
    source_article: Article,
    adapter=None,
) -> tuple[AnalysisRun, ExtractionResult]:
    """Run the versioned extraction task and retain attempt provenance.

    Callers can inject a deterministic adapter for tests. The default adapter
    only contacts a locally configured Ollama endpoint and never falls back to
    a cloud inference provider.
    """
    provider = adapter or OllamaLanguageModel()
    # Analyse one immutable revision so evidence spans stay valid if the article
    # is later revised.
    revision = current_revision(source_article)
    run = record_run(
        source_article=source_article,
        article_revision=revision,
        model_version=getattr(provider, "model_version", "local-model-unreported"),
        prompt_version=PROMPT_VERSION,
        schema_version=DEFAULT_EXTRACTION_SCHEMA_ID,
    )
    try:
        prompt = render_extraction_prompt(
            article_title=revision.title,
            article_text=revision.body,
        )
        proposed = provider.analyze(prompt, ExtractionResult)
        result = validate_evidence_spans(
            ExtractionResult.model_validate(proposed), revision.body
        )
    except Exception:
        run.status = AnalysisRun.Status.FAILED
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        raise

    run.status = AnalysisRun.Status.COMPLETED
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "completed_at"])
    return run, result
