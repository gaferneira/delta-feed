from django.db.models import Q

from delta_feed.core.guide_eligibility import find_eligibility_matches
from delta_feed.guides.models import GuideDefinition, GuideEntry, GuideProposal
from delta_feed.knowledge.models import Claim


def generate_guide_proposals_for_entity(entity, analysis_run):
    """Create pending add-entry proposals for deterministic criteria matches.

    This function never accepts proposals or mutates guide entries. Replaying a
    completed analysis returns the existing proposal instead of duplicating it.
    """
    article = analysis_run.source_article
    text_fields = [
        ("entity name", entity.name),
        ("entity type", entity.type),
        *(
            ("entity alias", alias)
            for alias in entity.aliases
            if isinstance(alias, str)
        ),
        ("source article title", article.title),
        ("source article body", article.body),
    ]
    proposals = []
    for guide in GuideDefinition.objects.filter(is_archived=False).iterator():
        matches = find_eligibility_matches(guide.eligibility_criteria, text_fields)
        if not matches:
            continue

        matched_criteria = list(dict.fromkeys(criterion for criterion, _ in matches))
        matched_fields = list(dict.fromkeys(label for _, label in matches))
        evidence = [
            {
                "article_id": article.pk,
                "url": article.url,
                "title": article.title,
                "analysis_run_id": analysis_run.pk,
                "entity_id": entity.pk,
                "entity_name": entity.name,
                "matched_criteria": matched_criteria,
                "matched_fields": matched_fields,
            }
        ]
        proposed_entry = {
            "entity_name": entity.name,
            "suitability": "",
            "requirements": [],
            "caveats": [],
            "evidence": evidence,
            "review_metadata": {
                "proposal_status": GuideProposal.Status.PENDING,
                "entity_id": entity.pk,
                "analysis_run_id": analysis_run.pk,
            },
        }
        reasoning = (
            "Deterministic keyword match for eligibility criteria: "
            f"{', '.join(matched_criteria)}. Matched in: {', '.join(matched_fields)}. "
            "This is a reviewable proposal, not a recommendation."
        )
        proposal, _created = GuideProposal.objects.get_or_create(
            guide=guide,
            entity=entity,
            analysis_run=analysis_run,
            proposal_type=GuideProposal.ProposalType.ADD,
            defaults={
                "source_article": article,
                "proposed_entry": proposed_entry,
                "evidence": evidence,
                "reasoning": reasoning,
            },
        )
        proposals.append(proposal)
    return proposals


def _retirement_marker(claim) -> bool:
    # Deterministic scope markers only; a failed source/link is not evidence of
    # discontinuation. Explicit availability values or a leading marker qualify.
    availability = (claim.availability or "").strip().casefold().replace("_", "-")
    if availability in {"deprecated", "discontinued", "retired", "end-of-life"}:
        return True
    text = claim.claim_text.lstrip().casefold()
    return any(
        text.startswith(marker)
        for marker in ("[deprecated]", "[discontinued]", "[retired]")
    )


def generate_guide_update_proposals_for_claim(claim, analysis_run):
    """Create pending, evidence-backed proposals for an already tracked entity."""
    if _retirement_marker(claim):
        proposal_type = GuideProposal.ProposalType.RETIRE
    elif claim.classification == Claim.Classification.REFINEMENT:
        proposal_type = GuideProposal.ProposalType.UPDATE
    elif claim.classification == Claim.Classification.CONTRADICTION:
        proposal_type = GuideProposal.ProposalType.WARNING
    else:
        return []

    article = analysis_run.source_article
    evidence = {
        "claim_id": claim.pk,
        "entity_id": claim.entity_id,
        "analysis_run_id": analysis_run.pk,
        "article_id": article.pk,
        "article_revision_id": analysis_run.article_revision_id,
        "url": article.url,
        "title": article.title,
        "quote": claim.evidence_text,
        "start": claim.evidence_start,
        "end": claim.evidence_end,
        "classification": claim.classification,
        "scope": {
            "version": claim.version,
            "platform": claim.platform,
            "availability": claim.availability,
        },
    }
    proposals = []
    entries = GuideEntry.objects.filter(
        guide__is_archived=False,
        is_retired=False,
    ).filter(
        Q(entity=claim.entity)
        | Q(entity__isnull=True, entity_name__iexact=claim.entity.name)
    ).select_related("guide")
    for entry in entries.iterator():
        if proposal_type == GuideProposal.ProposalType.UPDATE:
            proposed_entry = {"suitability": claim.claim_text}
            reasoning = "A refinement adds scoped detail to this tracked entry."
        elif proposal_type == GuideProposal.ProposalType.WARNING:
            warning = (
                "⚠ potentially outdated: newer contradictory evidence says: "
                f"{claim.claim_text}"
            )
            proposed_entry = {"warning": warning}
            reasoning = "Contradictory evidence may make this entry's advice outdated."
        else:
            proposed_entry = {"retire": True}
            reasoning = "The claim carries an explicit deprecation/discontinuation marker."

        proposal, _created = GuideProposal.objects.get_or_create(
            guide=entry.guide,
            entity=claim.entity,
            analysis_run=analysis_run,
            proposal_type=proposal_type,
            target_entry=entry,
            defaults={
                "source_article": article,
                "expected_revision": entry.revision,
                "proposed_entry": proposed_entry,
                "evidence": [evidence],
                "reasoning": reasoning,
            },
        )
        proposals.append(proposal)
    return proposals
