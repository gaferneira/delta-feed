from django.db import transaction
from django.utils import timezone

from delta_feed.analysis.models import AnalysisRun
from delta_feed.core.claim_delta import classify_claim_delta
from delta_feed.knowledge.models import Claim, Entity


class AnalysisRunNotCompleted(ValueError):
    """Claims may only be accepted from a run that finished successfully."""


class AnalysisRunWithoutRevision(ValueError):
    """The run predates revision tracking, so its evidence cannot be verified."""


def record_claim(entity, claim_data, analysis_run):
    """Classify and append a source-backed claim with its analysis provenance."""
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

    with transaction.atomic():
        # Serializes classification against other record_claim calls per entity
        # on databases with row-level locks; no external I/O occurs in the unit.
        Entity.objects.select_for_update().get(pk=entity.pk)
        existing = list(Claim.objects.filter(entity=entity))
        superseded_ids = {prior.supersedes_id for prior in existing if prior.supersedes_id}
        active_claims = [prior for prior in existing if prior.pk not in superseded_ids]
        candidate = {"claim_text": claim_text, **scope}
        classification = classify_claim_delta(candidate, active_claims)
        supersedes = None
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
        )
        from delta_feed.guides.use_cases import (
            generate_guide_update_proposals_for_claim,
        )

        generate_guide_update_proposals_for_claim(claim, analysis_run)
        return claim
