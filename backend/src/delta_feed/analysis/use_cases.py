from django.conf import settings
from django.db.models import Exists, OuterRef
from django.utils import timezone

from delta_feed.analysis.contracts.extraction import (
    ExtractionResult,
    resolve_evidence,
)
from delta_feed.analysis.models import DEFAULT_EXTRACTION_SCHEMA_ID, AnalysisRun
from delta_feed.analysis.prompts.extraction import (
    PROMPT_VERSION,
    render_extraction_prompt,
)
from delta_feed.analysis.providers import (
    InferenceUnavailableError,
    configured_language_model,
)
from delta_feed.content.models import Article, ArticleRevision
from delta_feed.content.revisions import current_revision
from delta_feed.jobs.models import Job
from delta_feed.jobs.services import enqueue_job


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

    Callers can inject a deterministic adapter for tests. Otherwise only the
    explicitly configured provider is used; there is no fallback provider.
    """
    provider = adapter or configured_language_model()
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
    # A prefix keeps evidence offsets valid against the full revision body.
    max_chars = settings.ANALYSIS_MAX_BODY_CHARS
    text = revision.body[:max_chars] if max_chars else revision.body
    try:
        prompt = render_extraction_prompt(article_title=revision.title, article_text=text)
        proposed = provider.analyze(prompt, ExtractionResult)
        result = ExtractionResult.model_validate(proposed)
        output = resolve_evidence(result, text)
    except Exception as error:
        run.status = AnalysisRun.Status.FAILED
        run.failure_reason = (
            AnalysisRun.FailureReason.INFERENCE_UNAVAILABLE
            if isinstance(error, InferenceUnavailableError)
            else AnalysisRun.FailureReason.INVALID_OUTPUT
        )
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "failure_reason", "completed_at"])
        raise

    output["truncated"] = len(text) < len(revision.body)
    run.status = AnalysisRun.Status.COMPLETED
    run.output = output
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "output", "completed_at"])
    return run, result


EXTRACT_JOB_TYPE = "analysis.extract"
# Small batches keep the priority order fresh as new articles arrive.
EXTRACT_BATCH_SIZE = 5


def _budgeted_runs_today(now=None):
    """Runs that reached the model today; provider outages do not spend the budget."""
    start = timezone.localtime(now or timezone.now()).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return AnalysisRun.objects.filter(started_at__gte=start).exclude(
        failure_reason=AnalysisRun.FailureReason.INFERENCE_UNAVAILABLE
    )


def unanalysed_articles():
    """Articles whose current revision has no settled run (completed or invalid output)."""
    settled = AnalysisRun.objects.filter(
        source_article=OuterRef("pk"),
        article_revision__version=OuterRef("current_version"),
        status__in=[AnalysisRun.Status.COMPLETED, AnalysisRun.Status.FAILED],
    ).exclude(failure_reason=AnalysisRun.FailureReason.INFERENCE_UNAVAILABLE)
    return Article.objects.exclude(Exists(settled))


def schedule_due_analysis(now=None) -> list[int]:
    """Enqueue extraction for the highest-priority unanalysed articles; returns their ids.

    Nothing is queued while the provider is unconfigured, while an extraction job is
    still pending or leased, or once the daily budget is spent. Current articles come
    first, newest discovered first; quiet backfill comes last and only seeds the baseline.
    """
    if not configured_language_model().is_configured():
        return []
    if Job.objects.filter(
        type=EXTRACT_JOB_TYPE, status__in=[Job.Status.PENDING, Job.Status.RUNNING]
    ).exists():
        return []
    remaining = settings.ANALYSIS_DAILY_BUDGET - _budgeted_runs_today(now).count()
    if remaining <= 0:
        return []
    article_ids = list(
        unanalysed_articles()
        .order_by("is_backfill", "-created_at", "-id")
        .values_list("pk", flat=True)[: min(remaining, EXTRACT_BATCH_SIZE)]
    )
    for article_id in article_ids:
        enqueue_job(
            job_type=EXTRACT_JOB_TYPE,
            payload={"article_id": article_id},
            handler_name="analysis.extract_article",
        )
    return article_ids


def extract_article_job(payload: dict) -> dict:
    """Worker handler. Provider outages raise for a durable retry with backoff;
    invalid model output is recorded on the run and not retried automatically."""
    article = Article.objects.filter(pk=payload.get("article_id")).first()
    if article is None:
        return {"status": "article_missing"}
    if _budgeted_runs_today().count() >= settings.ANALYSIS_DAILY_BUDGET:
        return {"status": "budget_exhausted"}
    try:
        run, result = extract_article(source_article=article)
    except InferenceUnavailableError:
        raise
    except ValueError:
        return {"status": "invalid_output"}
    return {
        "status": "completed",
        "run_id": run.pk,
        "entities": len(result.entities),
        "claims": len(result.claims),
    }
