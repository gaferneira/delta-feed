from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from delta_feed.analysis.models import AnalysisRun
from delta_feed.core.claim_delta import classify_claim_delta
from delta_feed.core.claim_fingerprint import claim_fingerprint
from delta_feed.knowledge.models import Claim, Entity


class AnalysisRunNotCompleted(ValueError):
    """Claims may only be accepted from a run that finished successfully."""


class AnalysisRunWithoutRevision(ValueError):
    """The run predates revision tracking, so its evidence cannot be verified."""


@dataclass(frozen=True)
class ClaimDecision:
    """A comparison result decided outside this writer (fingerprint, model, ...)."""

    classification: str
    method: str
    matched_claim: Claim | None = None
    model_version: str = ""
    prompt_version: str = ""


def record_claim(entity, claim_data, analysis_run, *, decision=None):
    """Classify and append a source-backed claim with its analysis provenance.

    With ``decision`` the lexical classifier is skipped and the decision stored;
    without it the lexical classifier runs and the method stays ``manual``.
    """
    if analysis_run.status != AnalysisRun.Status.COMPLETED:
        raise AnalysisRunNotCompleted(
            "claims can only be recorded from a completed analysis run"
        )
    revision = analysis_run.article_revision
    if revision is None:
        raise AnalysisRunWithoutRevision(
            "analysis run has no recorded article revision to verify evidence against"
        )
    article = analysis_run.source_article
    # Spans index into the analysed revision, not the article's current text.
    body = revision.body
    claim_text = claim_data.get("claim_text", "")
    evidence_start = claim_data.get("evidence_start")
    evidence_end = claim_data.get("evidence_end")
    evidence_text = claim_data.get("evidence_text", "")

    if not isinstance(claim_text, str) or not claim_text.strip():
        raise ValueError("claim_text must be a non-empty string")
    if (
        not isinstance(evidence_start, int)
        or not isinstance(evidence_end, int)
        or evidence_start < 0
        or evidence_end <= evidence_start
        or evidence_end > len(body)
        or body[evidence_start:evidence_end] != evidence_text
        or not evidence_text
    ):
        raise ValueError("evidence span must match the article revision that was analysed")

    scope = {
        "version": claim_data.get("version"),
        "platform": claim_data.get("platform"),
        "availability": claim_data.get("availability"),
    }
    observed_at = claim_data.get("observed_at") or timezone.now()
    predicate = claim_data.get("predicate")
    value = claim_data.get("value")
    fingerprint = (
        claim_fingerprint(entity.pk, predicate, value, scope)
        if isinstance(predicate, str) and isinstance(value, str) and predicate and value
        else None
    )

    with transaction.atomic():
        # Serializes classification against other record_claim calls per entity
        # on databases with row-level locks; no external I/O occurs in the unit.
        Entity.objects.select_for_update().get(pk=entity.pk)
        existing = list(Claim.objects.filter(entity=entity))
        superseded_ids = {prior.supersedes_id for prior in existing if prior.supersedes_id}
        active_claims = [prior for prior in existing if prior.pk not in superseded_ids]
        supersedes = None
        comparison = {}
        if decision is not None:
            classification = decision.classification
            if classification == Claim.Classification.CONTRADICTION:
                supersedes = decision.matched_claim
            comparison = {
                "matched_claim": decision.matched_claim,
                "comparison_method": decision.method,
                "comparison_model_version": decision.model_version,
                "comparison_prompt_version": decision.prompt_version,
            }
        else:
            candidate = {"claim_text": claim_text, **scope}
            classification = classify_claim_delta(candidate, active_claims)
            if classification == Claim.Classification.CONTRADICTION:
                conflicts = [
                    prior
                    for prior in active_claims
                    if classify_claim_delta(candidate, [prior])
                    == Claim.Classification.CONTRADICTION
                ]
                if conflicts:
                    supersedes = max(conflicts, key=lambda prior: (prior.observed_at, prior.pk))

        claim = Claim.objects.create(
            entity=entity,
            **scope,
            claim_text=claim_text,
            source_article=article,
            evidence_start=evidence_start,
            evidence_end=evidence_end,
            evidence_text=evidence_text,
            observed_at=observed_at,
            analysis_run=analysis_run,
            classification=classification,
            supersedes=supersedes,
            predicate=predicate,
            value=value,
            fingerprint=fingerprint,
            **comparison,
        )
        from delta_feed.guides.use_cases import (
            generate_guide_update_proposals_for_claim,
        )

        generate_guide_update_proposals_for_claim(claim, analysis_run)
        return claim
