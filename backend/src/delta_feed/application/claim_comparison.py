"""Compare an article's claims about one entity with its baseline, then record them.

Order of work: deterministic tier (fingerprint, then lexical rules), one model call
outside any transaction for what is left, then one locked write that rechecks that
the baseline did not change. A claim the model cannot place is `unsure`, never
`duplicate`. Re-running with the same analysis run is safe.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from django.db import transaction
from django.utils import timezone

from delta_feed.analysis.contracts.comparison import (
    COMPARISON_SCHEMA_ID,
    ComparisonOutput,
    single_results,
    unknown_baseline_ids,
)
from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.prompts.comparison import (
    MAX_BASELINE_CLAIMS,
    PROMPT_VERSION,
    render_comparison_prompt,
)
from delta_feed.analysis.providers import InferenceUnavailableError
from delta_feed.core.claim_delta import SCOPE_FIELDS, classify_claim_delta_with_match
from delta_feed.core.claim_fingerprint import claim_fingerprint
from delta_feed.knowledge.models import Claim, Entity
from delta_feed.knowledge.use_cases import ClaimDecision, record_claim

MAX_ROUNDS = 2
_METHOD = Claim.ComparisonMethod
_CLASS = Claim.Classification


@dataclass
class ComparisonOutcome:
    written: list[Claim] = field(default_factory=list)
    # Claims already present from an earlier attempt (or repeated in the same article).
    skipped: int = 0
    # A model call was needed but the daily budget is spent; those claims stay unwritten.
    budget_exhausted: bool = False
    unwritten: int = 0

    @property
    def complete(self) -> bool:
        return self.unwritten == 0


def claim_data_from_extraction(claim: dict, analysis_run: AnalysisRun) -> dict:
    """Map one stored extraction claim to `record_claim` input (first evidence span)."""
    span = claim["evidence"][0]
    scope = claim.get("scope") or {}
    article = analysis_run.source_article
    return {
        "claim_text": f"{claim['predicate']}: {claim['value']}",
        "predicate": claim["predicate"],
        "value": claim["value"],
        **{name: scope.get(name) for name in SCOPE_FIELDS},
        "evidence_start": span["start"],
        "evidence_end": span["end"],
        "evidence_text": span["quote"],
        "observed_at": article.source_published_at or analysis_run.completed_at,
    }


def active_baseline(entity) -> list[Claim]:
    """The entity's claims that are not superseded, newest first."""
    superseded = Claim.objects.filter(entity=entity, supersedes__isnull=False).values(
        "supersedes"
    )
    return list(
        Claim.objects.filter(entity=entity).exclude(pk__in=superseded).order_by("-pk")
    )


def _scope(data):
    return {name: data.get(name) for name in SCOPE_FIELDS}


def _fingerprint(entity, data):
    return claim_fingerprint(entity.pk, data["predicate"], data["value"], _scope(data))


def _unsure(method, model_version="", prompt_version=""):
    return ClaimDecision(
        classification=_CLASS.UNSURE,
        method=method,
        model_version=model_version,
        prompt_version=prompt_version,
    )


def _deterministic(entity, entries, baseline):
    """Decide what fingerprints and lexical rules can; returns (decisions, undecided)."""
    if not baseline:
        first = ClaimDecision(classification=_CLASS.NEW, method=_METHOD.FIRST_SIGHTING)
        return {index: first for index, _, _ in entries}, []
    by_fingerprint = {}
    for claim in reversed(baseline):  # oldest first: credit goes to the first article
        if claim.fingerprint:
            by_fingerprint.setdefault(claim.fingerprint, claim)
    decisions, undecided = {}, []
    for entry in entries:
        index, data, fingerprint = entry
        matched = by_fingerprint.get(fingerprint)
        if matched is not None:
            decisions[index] = ClaimDecision(
                classification=_CLASS.DUPLICATE,
                method=_METHOD.FINGERPRINT,
                matched_claim=matched,
            )
            continue
        classification, matched = classify_claim_delta_with_match(
            {"claim_text": data["claim_text"], **_scope(data)}, baseline
        )
        if classification != _CLASS.NEW:
            decisions[index] = ClaimDecision(
                classification=classification,
                method=_METHOD.LEXICAL,
                matched_claim=matched,
            )
        else:
            undecided.append(entry)
    return decisions, undecided


def _ask_model(entity, undecided, baseline, analysis_run, provider):
    """One compare_claims call for all undecided claims; never inside a transaction."""
    # Imported here because analysis.use_cases imports this module.
    from delta_feed.analysis.use_cases import record_run

    model_version = getattr(provider, "model_version", "local-model-unreported")
    run = record_run(
        source_article=analysis_run.source_article,
        article_revision=analysis_run.article_revision,
        kind=AnalysisRun.Kind.COMPARE,
        model_version=model_version,
        prompt_version=PROMPT_VERSION,
        schema_version=COMPARISON_SCHEMA_ID,
    )
    unsure = _unsure(_METHOD.MODEL, model_version, PROMPT_VERSION)
    try:
        prompt = render_comparison_prompt(
            entity, [data for _, data, _ in undecided], baseline[:MAX_BASELINE_CLAIMS]
        )
        proposed = provider.analyze(prompt, ComparisonOutput)
        output = ComparisonOutput.model_validate(proposed)
    except Exception as error:
        unavailable = isinstance(error, InferenceUnavailableError)
        run.status = AnalysisRun.Status.FAILED
        run.failure_reason = (
            AnalysisRun.FailureReason.INFERENCE_UNAVAILABLE
            if unavailable
            else AnalysisRun.FailureReason.INVALID_OUTPUT
        )
        run.output = {} if unavailable else {"error": str(error)}
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "failure_reason", "output", "completed_at"])
        if unavailable:
            raise
        return {index: unsure for index, _, _ in undecided}

    baseline_by_id = {claim.pk: claim for claim in baseline[:MAX_BASELINE_CLAIMS]}
    # A claim the model skipped, answered twice or matched to an unknown id is
    # unsure; the other answers are still used.
    usable = single_results(output, len(undecided))
    unplaced = unknown_baseline_ids(output, baseline_by_id) | (
        set(range(len(undecided))) - set(usable)
    )
    decisions = {
        index: unsure
        for position, (index, _, _) in enumerate(undecided)
        if position in unplaced
    }
    for position, result in usable.items():
        index = undecided[position][0]
        if position in unplaced:
            continue
        decisions[index] = ClaimDecision(
            classification=result.classification,
            method=_METHOD.MODEL,
            matched_claim=baseline_by_id.get(result.matched_claim_id),
            model_version=model_version,
            prompt_version=PROMPT_VERSION,
        )
    run.status = AnalysisRun.Status.COMPLETED
    run.output = {
        **output.model_dump(mode="json"),
        "entity_id": entity.pk,
        "unplaced_claim_indexes": sorted(unplaced),
    }
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "output", "completed_at"])
    return decisions


def _credit_first(decision):
    """Point a duplicate at the first claim that stated the fact, not at a later repeat."""
    matched = decision.matched_claim
    if decision.classification != _CLASS.DUPLICATE or matched is None:
        return decision
    seen = set()
    while (
        matched.classification == _CLASS.DUPLICATE
        and matched.matched_claim_id
        and matched.pk not in seen
    ):
        seen.add(matched.pk)
        matched = matched.matched_claim
    return replace(decision, matched_claim=matched)


def _write(entity, entries, decisions, analysis_run, outcome):
    """Write decided claims in extraction order; called inside the entity lock."""
    article = analysis_run.source_article
    for index, data, fingerprint in entries:
        decision = decisions.get(index)
        if decision is None:
            outcome.unwritten += 1
            continue
        if Claim.objects.filter(
            entity=entity, source_article=article, fingerprint=fingerprint
        ).exists():
            outcome.skipped += 1
            continue
        outcome.written.append(
            record_claim(entity, data, analysis_run, decision=_credit_first(decision))
        )
    return outcome


def compare_and_record(
    entity,
    claims: list[dict],
    analysis_run: AnalysisRun,
    provider,
    *,
    budget_available: Callable[[], bool] | None = None,
) -> ComparisonOutcome:
    """Compare `claims` (record_claim input dicts) with the entity baseline and write them.

    `budget_available` is asked right before a model call; when it says no, the claims
    that need the model stay unwritten and `budget_exhausted` is set. Provider outages
    raise InferenceUnavailableError with nothing written.
    """
    article = analysis_run.source_article
    prints = [_fingerprint(entity, data) for data in claims]
    done = set(
        Claim.objects.filter(
            entity=entity, source_article=article, fingerprint__in=prints
        ).values_list("fingerprint", flat=True)
    )
    entries = []
    for index, (data, fingerprint) in enumerate(zip(claims, prints, strict=True)):
        if fingerprint not in done:
            done.add(fingerprint)
            entries.append((index, data, fingerprint))
    outcome = ComparisonOutcome(skipped=len(claims) - len(entries))
    if not entries:
        return outcome

    for round_number in range(1, MAX_ROUNDS + 1):
        baseline = active_baseline(entity)
        version = baseline[0].pk if baseline else 0
        decisions, undecided = _deterministic(entity, entries, baseline)
        exhausted = False
        if undecided:
            if len(baseline) > MAX_BASELINE_CLAIMS:
                # Too many claims to show the model; reviewable instead of guessed.
                decisions.update(
                    {index: _unsure(_METHOD.LEXICAL) for index, _, _ in undecided}
                )
            elif budget_available is not None and not budget_available():
                exhausted = True
            else:
                decisions.update(
                    _ask_model(entity, undecided, baseline, analysis_run, provider)
                )
        with transaction.atomic():
            Entity.objects.select_for_update().get(pk=entity.pk)
            current = active_baseline(entity)
            if (current[0].pk if current else 0) != version:
                if round_number < MAX_ROUNDS:
                    continue
                # Out of rounds: deterministic tier against the fresh baseline, no model call.
                decisions, undecided = _deterministic(entity, entries, current)
                if not exhausted:
                    decisions.update(
                        {index: _unsure(_METHOD.LEXICAL) for index, _, _ in undecided}
                    )
            outcome.budget_exhausted = exhausted
            return _write(entity, entries, decisions, analysis_run, outcome)
    return outcome  # pragma: no cover - the last round always returns
