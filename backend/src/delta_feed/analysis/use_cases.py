from datetime import timedelta

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
from delta_feed.application.claim_comparison import (
    claim_data_from_extraction,
    compare_and_record,
)
from delta_feed.application.mention_resolution import queue_mentions
from delta_feed.content.models import Article, ArticleRevision
from delta_feed.content.revisions import current_revision
from delta_feed.guides.use_cases import generate_guide_proposals_for_entity
from delta_feed.jobs.models import Job
from delta_feed.jobs.services import enqueue_job
from delta_feed.knowledge.models import ExtractedMention


def record_run(
    *,
    source_article: Article,
    article_revision: ArticleRevision | None = None,
    status: str = AnalysisRun.Status.RUNNING,
    model_version: str,
    prompt_version: str,
    schema_version: str = DEFAULT_EXTRACTION_SCHEMA_ID,
    kind: str = AnalysisRun.Kind.EXTRACT,
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
        kind=kind,
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
        update_fields = ["status", "failure_reason", "completed_at"]
        if run.failure_reason == AnalysisRun.FailureReason.INVALID_OUTPUT:
            run.output = {"error": str(error)[:2000]}
            update_fields.append("output")
        run.save(update_fields=update_fields)
        raise

    output["truncated"] = len(text) < len(revision.body)
    run.status = AnalysisRun.Status.COMPLETED
    run.output = output
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "output", "completed_at"])
    return run, result


EXTRACT_JOB_TYPE = "analysis.extract"
COMPARE_JOB_TYPE = "analysis.compare"
COMPARE_GROUP_JOB_TYPE = "analysis.compare_group"
# Small batches keep the priority order fresh as new articles arrive.
EXTRACT_BATCH_SIZE = 5
COMPARE_BATCH_SIZE = 5
_OPEN_JOB_STATUSES = [Job.Status.PENDING, Job.Status.RUNNING]


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
        kind=AnalysisRun.Kind.EXTRACT,
        status__in=[AnalysisRun.Status.COMPLETED, AnalysisRun.Status.FAILED],
    ).exclude(failure_reason=AnalysisRun.FailureReason.INFERENCE_UNAVAILABLE)
    return Article.objects.exclude(Exists(settled))


def _budget_available() -> bool:
    return _budgeted_runs_today().count() < settings.ANALYSIS_DAILY_BUDGET


def enqueue_compare_run(run_id: int) -> Job | None:
    """Queue comparison of one extraction run unless one is already pending or running."""
    if Job.objects.filter(
        type=COMPARE_JOB_TYPE, status__in=_OPEN_JOB_STATUSES, payload__run_id=run_id
    ).exists():
        return None
    return enqueue_job(
        job_type=COMPARE_JOB_TYPE,
        payload={"run_id": run_id},
        handler_name="analysis.compare_run",
    )


def enqueue_compare_group(
    normalized_name: str, entity_type: str, analysis_run_id: int, delay_seconds: int = 0
) -> Job | None:
    """Queue comparison of one resolved mention group of a run, once at a time.

    A delay leaves room to undo the decision before the comparison runs."""
    payload = {
        "normalized_name": normalized_name,
        "entity_type": entity_type.strip().casefold(),
        "analysis_run_id": analysis_run_id,
    }
    if Job.objects.filter(
        type=COMPARE_GROUP_JOB_TYPE,
        status__in=_OPEN_JOB_STATUSES,
        payload__normalized_name=payload["normalized_name"],
        payload__entity_type=payload["entity_type"],
        payload__analysis_run_id=analysis_run_id,
    ).exists():
        return None
    return enqueue_job(
        job_type=COMPARE_GROUP_JOB_TYPE,
        payload=payload,
        handler_name="analysis.compare_mention_group",
        run_after=timezone.now() + timedelta(seconds=delay_seconds) if delay_seconds else None,
    )


def runs_awaiting_comparison():
    return AnalysisRun.objects.filter(
        kind=AnalysisRun.Kind.EXTRACT,
        status=AnalysisRun.Status.COMPLETED,
        compared_at__isnull=True,
    )


def _schedule_due_comparisons(remaining: int) -> list[int]:
    run_ids = list(
        runs_awaiting_comparison().order_by("-started_at", "-id").values_list("pk", flat=True)[
            : min(remaining, COMPARE_BATCH_SIZE)
        ]
    )
    return [run_id for run_id in run_ids if enqueue_compare_run(run_id) is not None]


def schedule_due_analysis(now=None) -> list[int]:
    """Enqueue extraction for the highest-priority unanalysed articles; returns their ids.

    Nothing is queued while the provider is unconfigured, while an extraction job is
    still pending or leased, or once the daily budget is spent. Current articles come
    first, newest discovered first; quiet backfill comes last and only seeds the baseline.
    """
    if not configured_language_model().is_configured():
        return []
    remaining = settings.ANALYSIS_DAILY_BUDGET - _budgeted_runs_today(now).count()
    if remaining <= 0:
        return []
    # Completed extractions whose claims are not yet compared, e.g. after an exhausted budget.
    _schedule_due_comparisons(remaining)
    if Job.objects.filter(type=EXTRACT_JOB_TYPE, status__in=_OPEN_JOB_STATUSES).exists():
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
        run, _ = extract_article(source_article=article)
    except InferenceUnavailableError:
        raise
    except ValueError:
        return {"status": "invalid_output"}
    enqueue_compare_run(run.pk)
    return {
        "status": "completed",
        "run_id": run.pk,
        "entities": len(run.output["entities"]),
        "claims": len(run.output["claims"]),
        "dropped": len(run.output["dropped"]),
    }


def _compare_mentions(run: AnalysisRun, mentions) -> tuple[list[ExtractedMention], bool]:
    """Compare and write the claims of resolved mentions; returns (compared, budget_exhausted).

    A mention's `compared_at` is set only when every one of its claims is written
    or recorded unsure. Provider outages raise for a durable retry.
    """
    provider = configured_language_model()
    compared, exhausted = [], False
    for mention in mentions:
        claims = [claim_data_from_extraction(claim, run) for claim in mention.claims]
        outcome = compare_and_record(
            mention.entity, claims, run, provider, budget_available=_budget_available
        )
        if outcome.complete:
            mention.compared_at = timezone.now()
            mention.save(update_fields=["compared_at"])
            compared.append(mention)
        exhausted = exhausted or outcome.budget_exhausted
    return compared, exhausted


def _settle_run(run: AnalysisRun) -> bool:
    """Mark the run compared when no resolved mention is still waiting.

    Pending mentions do not block it (the group job handles them later) and
    dismissed mentions never write claims.
    """
    waiting = run.mentions.filter(
        status=ExtractedMention.Status.RESOLVED, compared_at__isnull=True
    ).exists()
    if waiting:
        return False
    run.compared_at = timezone.now()
    run.save(update_fields=["compared_at"])
    return True


def compare_run_job(payload: dict) -> dict:
    """Worker handler: resolve and store a completed extraction's mentions, then compare
    and write the claims of the resolved ones. Provider outages raise for a durable retry."""
    run = (
        AnalysisRun.objects.select_related("source_article", "article_revision")
        .filter(
            pk=payload.get("run_id"),
            kind=AnalysisRun.Kind.EXTRACT,
            status=AnalysisRun.Status.COMPLETED,
        )
        .first()
    )
    if run is None:
        return {"status": "run_missing"}
    if run.compared_at is not None:
        return {"status": "already_compared"}
    output = run.output or {}
    stored = queue_mentions(run, output.get("entities", []), output.get("claims", []))
    ready = [
        mention
        for mention in ExtractedMention.objects.filter(
            analysis_run=run,
            status=ExtractedMention.Status.RESOLVED,
            compared_at__isnull=True,
        ).select_related("entity")
    ]
    _, exhausted = _compare_mentions(run, ready)
    result = {
        "run_id": run.pk,
        "mentions": len(stored),
        "pending_mentions": sum(1 for m in stored if m.status == ExtractedMention.Status.PENDING),
    }
    if exhausted:
        return {"status": "budget_exhausted", **result}
    return {"status": "completed", "compared": _settle_run(run), **result}


def compare_mention_group_job(payload: dict) -> dict:
    """Worker handler: compare the claims of one run for a resolved mention group, offer
    guide proposals for its entities, and mark the mentions compared."""
    run = (
        AnalysisRun.objects.select_related("source_article", "article_revision")
        .filter(pk=payload.get("analysis_run_id"), kind=AnalysisRun.Kind.EXTRACT)
        .first()
    )
    if run is None:
        return {"status": "run_missing"}
    entity_type = str(payload.get("entity_type", "")).strip().casefold()
    mentions = [
        mention
        for mention in ExtractedMention.objects.filter(
            analysis_run=run,
            normalized_name=payload.get("normalized_name"),
            status=ExtractedMention.Status.RESOLVED,
            compared_at__isnull=True,
        ).select_related("entity")
        if mention.entity_type.strip().casefold() == entity_type
    ]
    compared, exhausted = _compare_mentions(run, mentions)
    entities = {mention.entity_id: mention.entity for mention in compared}
    for entity in entities.values():
        generate_guide_proposals_for_entity(entity, run)
    if run.compared_at is None and not exhausted:
        _settle_run(run)
    status = "budget_exhausted" if exhausted else "completed"
    return {"status": status, "run_id": run.pk, "compared_mentions": len(compared)}
