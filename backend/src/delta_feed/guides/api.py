from typing import Any

from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest
from ninja import Field, Router, Schema
from ninja.errors import HttpError
from ninja.responses import Status

from delta_feed.guides.models import (
    GuideDefinition,
    GuideEntry,
    GuideProposal,
    GuideRevision,
)
from delta_feed.knowledge.models import Entity

router = Router(tags=["guides"])


class GuideDefinitionCreate(Schema):
    title: str = Field(min_length=1, max_length=250)
    purpose: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    topic_links: list[str] = Field(default_factory=list)
    eligibility_criteria: list[str] = Field(default_factory=list)
    sections: list[dict[str, Any]] = Field(default_factory=list)


class GuideDefinitionPatch(Schema):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    purpose: str | None = Field(default=None, min_length=1)
    audience: str | None = Field(default=None, min_length=1)
    topic_links: list[str] | None = None
    eligibility_criteria: list[str] | None = None
    sections: list[dict[str, Any]] | None = None


class GuideDefinitionOut(Schema):
    id: int
    title: str
    purpose: str
    audience: str
    topic_links: list[str]
    eligibility_criteria: list[str]
    sections: list[dict[str, Any]]
    created_at: Any
    updated_at: Any


class GuideDefinitionList(Schema):
    items: list[GuideDefinitionOut]


class GuideEntryCreate(Schema):
    entity_id: int | None = None
    entity_name: str = Field(min_length=1, max_length=250)
    suitability: str = ""
    requirements: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    review_metadata: dict[str, Any] = Field(default_factory=dict)
    personal_prose: str = ""


class GuideEntryEdit(Schema):
    expected_revision: int = Field(ge=1)
    entity_name: str | None = Field(default=None, min_length=1, max_length=250)
    suitability: str | None = None
    requirements: list[str] | None = None
    caveats: list[str] | None = None
    evidence: list[dict[str, Any]] | None = None
    review_metadata: dict[str, Any] | None = None
    personal_prose: str | None = None


class GuideEntryOut(Schema):
    id: int
    guide_id: int
    entity_id: int | None
    entity_name: str
    suitability: str
    requirements: list[str]
    caveats: list[str]
    evidence: list[dict[str, Any]]
    review_metadata: dict[str, Any]
    personal_prose: str
    revision: int
    is_retired: bool
    created_at: Any
    updated_at: Any


class GuideRevisionOut(Schema):
    version: int
    snapshot: dict[str, Any]
    changed_by_id: int
    created_at: Any


class GuideRevisionList(Schema):
    items: list[GuideRevisionOut]


class GuideProposalOut(Schema):
    id: int
    guide_id: int
    entity_id: int
    analysis_run_id: int
    source_article_id: int
    proposal_type: str
    target_entry_id: int | None
    expected_revision: int | None
    proposed_entry: dict[str, Any]
    evidence: list[dict[str, Any]]
    reasoning: str
    status: str
    created_at: Any


class GuideProposalList(Schema):
    items: list[GuideProposalOut]


def _owned_guide(request: HttpRequest, guide_id: int) -> GuideDefinition:
    try:
        return GuideDefinition.objects.get(pk=guide_id, owner=request.user)
    except GuideDefinition.DoesNotExist as exc:
        raise HttpError(404, "Guide not found") from exc


def _owned_entry(request: HttpRequest, entry_id: int) -> GuideEntry:
    try:
        return GuideEntry.objects.select_related("guide").get(
            pk=entry_id, guide__owner=request.user
        )
    except GuideEntry.DoesNotExist as exc:
        raise HttpError(404, "Guide entry not found") from exc


def _entry_snapshot(entry: GuideEntry) -> dict[str, Any]:
    return {
        "guide_id": entry.guide_id,
        "entity_id": entry.entity_id,
        "entity_name": entry.entity_name,
        "suitability": entry.suitability,
        "requirements": entry.requirements,
        "caveats": entry.caveats,
        "evidence": entry.evidence,
        "review_metadata": entry.review_metadata,
        "personal_prose": entry.personal_prose,
        "is_retired": entry.is_retired,
    }


def _record_revision(entry: GuideEntry, user) -> GuideRevision:
    return GuideRevision.objects.create(
        entry=entry,
        version=entry.revision,
        snapshot=_entry_snapshot(entry),
        changed_by=user,
    )


def _create_entry_with_revision(*, guide, user, entry_data):
    entry = GuideEntry.objects.create(guide=guide, **entry_data)
    _record_revision(entry, user)
    return entry


def _edit_entry(*, request: HttpRequest, entry_id: int, payload: GuideEntryEdit):
    values = payload.model_dump(
        exclude_unset=True, exclude={"expected_revision"}, exclude_none=True
    )
    if not values:
        raise HttpError(422, "At least one entry field must be provided")

    with transaction.atomic():
        try:
            entry = GuideEntry.objects.select_for_update().get(
                pk=entry_id, guide__owner=request.user
            )
        except GuideEntry.DoesNotExist as exc:
            raise HttpError(404, "Guide entry not found") from exc
        if entry.is_retired:
            raise HttpError(404, "Guide entry not found")
        if entry.revision != payload.expected_revision:
            raise HttpError(409, "Guide entry revision is stale")

        for field, value in values.items():
            setattr(entry, field, value)
        entry.revision += 1
        entry.save(update_fields=[*values, "revision", "updated_at"])
        _record_revision(entry, request.user)
    return entry


@router.get("/definitions", response=GuideDefinitionList)
def list_guides(request: HttpRequest):
    return {
        "items": GuideDefinition.objects.filter(owner=request.user, is_archived=False)
    }


@router.post("/definitions", response={201: GuideDefinitionOut})
def create_guide(request: HttpRequest, payload: GuideDefinitionCreate):
    guide = GuideDefinition.objects.create(owner=request.user, **payload.model_dump())
    return Status(201, guide)


@router.get("/definitions/{guide_id}", response=GuideDefinitionOut)
def get_guide(request: HttpRequest, guide_id: int):
    guide = _owned_guide(request, guide_id)
    if guide.is_archived:
        raise HttpError(404, "Guide not found")
    return guide


@router.patch("/definitions/{guide_id}", response=GuideDefinitionOut)
def update_guide(request: HttpRequest, guide_id: int, payload: GuideDefinitionPatch):
    guide = _owned_guide(request, guide_id)
    if guide.is_archived:
        raise HttpError(404, "Guide not found")
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        raise HttpError(422, "At least one guide field must be provided")
    for field, value in values.items():
        setattr(guide, field, value)
    guide.save(update_fields=[*values, "updated_at"])
    return guide


@router.delete("/definitions/{guide_id}", response={204: None})
def archive_guide(request: HttpRequest, guide_id: int):
    guide = _owned_guide(request, guide_id)
    if not guide.is_archived:
        guide.is_archived = True
        guide.save(update_fields=["is_archived", "updated_at"])
    return Status(204, None)


@router.get("/definitions/{guide_id}/entries", response=list[GuideEntryOut])
def list_entries(request: HttpRequest, guide_id: int):
    guide = _owned_guide(request, guide_id)
    return guide.entries.filter(is_retired=False)


@router.post("/definitions/{guide_id}/entries", response={201: GuideEntryOut})
def create_entry(request: HttpRequest, guide_id: int, payload: GuideEntryCreate):
    guide = _owned_guide(request, guide_id)
    if guide.is_archived:
        raise HttpError(404, "Guide not found")
    entry_data = payload.model_dump()
    entity_id = entry_data.pop("entity_id")
    if entity_id is not None:
        try:
            entry_data["entity"] = Entity.objects.get(pk=entity_id)
        except Entity.DoesNotExist as exc:
            raise HttpError(404, "Entity not found") from exc
    with transaction.atomic():
        entry = _create_entry_with_revision(
            guide=guide,
            user=request.user,
            entry_data=entry_data,
        )
    return Status(201, entry)


@router.get("/entries/{entry_id}", response=GuideEntryOut)
def get_entry(request: HttpRequest, entry_id: int):
    return _owned_entry(request, entry_id)


@router.patch("/entries/{entry_id}", response=GuideEntryOut)
def patch_entry(request: HttpRequest, entry_id: int, payload: GuideEntryEdit):
    return _edit_entry(request=request, entry_id=entry_id, payload=payload)


@router.post("/entries/{entry_id}/edit", response=GuideEntryOut)
def edit_entry(request: HttpRequest, entry_id: int, payload: GuideEntryEdit):
    return _edit_entry(request=request, entry_id=entry_id, payload=payload)


@router.delete("/entries/{entry_id}", response={204: None})
def retire_entry(request: HttpRequest, entry_id: int, expected_revision: int):
    with transaction.atomic():
        try:
            entry = GuideEntry.objects.select_for_update().get(
                pk=entry_id, guide__owner=request.user
            )
        except GuideEntry.DoesNotExist as exc:
            raise HttpError(404, "Guide entry not found") from exc
        if entry.revision != expected_revision:
            raise HttpError(409, "Guide entry revision is stale")
        if not entry.is_retired:
            entry.is_retired = True
            entry.revision += 1
            entry.save(update_fields=["is_retired", "revision", "updated_at"])
            _record_revision(entry, request.user)
    return Status(204, None)


@router.get("/proposals", response=GuideProposalList)
def list_proposals(request: HttpRequest):
    return {
        "items": GuideProposal.objects.filter(
            guide__owner=request.user,
            guide__is_archived=False,
            status=GuideProposal.Status.PENDING,
        ).select_related("guide", "entity", "analysis_run", "source_article")
    }


@router.post("/proposals/{proposal_id}/accept", response=GuideEntryOut)
def accept_proposal(request: HttpRequest, proposal_id: int):
    with transaction.atomic():
        try:
            proposal = (
                GuideProposal.objects.select_for_update()
                .select_related("guide")
                .get(pk=proposal_id, guide__owner=request.user)
            )
        except GuideProposal.DoesNotExist as exc:
            raise HttpError(404, "Guide proposal not found") from exc
        if proposal.status != GuideProposal.Status.PENDING:
            raise HttpError(409, "Guide proposal is no longer pending")
        if proposal.guide.is_archived:
            raise HttpError(404, "Guide not found")

        if proposal.proposal_type == GuideProposal.ProposalType.ADD:
            entry_data = GuideEntryCreate.model_validate(
                proposal.proposed_entry
            ).model_dump()
            entry_data.pop("entity_id", None)
            entry_data["entity"] = proposal.entity
            entry_data["review_metadata"] = {
                **entry_data["review_metadata"],
                "proposal_status": GuideProposal.Status.ACCEPTED,
                "accepted_proposal_id": proposal.pk,
            }
            entry = (
                GuideEntry.objects.select_for_update()
                .filter(guide=proposal.guide, is_retired=False)
                .filter(
                    Q(entity=proposal.entity)
                    | Q(
                        entity__isnull=True,
                        entity_name__iexact=proposal.entity.name,
                    )
                )
                .first()
            )
            if entry is None:
                entry = _create_entry_with_revision(
                    guide=proposal.guide,
                    user=request.user,
                    entry_data=entry_data,
                )
            else:
                # Keep editorial prose and existing manual fields intact. A proposal
                # may add evidence/context but cannot replace personal writing.
                merged_evidence = list(entry.evidence)
                for item in proposal.evidence:
                    if item not in merged_evidence:
                        merged_evidence.append(item)
                review_metadata = {
                    **entry.review_metadata,
                    **entry_data["review_metadata"],
                    "accepted_proposal_id": proposal.pk,
                }
                update_fields = ["evidence", "review_metadata", "revision", "updated_at"]
                entry.evidence = merged_evidence
                entry.review_metadata = review_metadata
                if entry.entity_id is None:
                    entry.entity = proposal.entity
                    update_fields.append("entity")
                entry.revision += 1
                entry.save(update_fields=update_fields)
                _record_revision(entry, request.user)
        else:
            if proposal.target_entry_id is None:
                raise HttpError(409, "Proposal target entry is no longer available")
            try:
                entry = GuideEntry.objects.select_for_update().get(
                    Q(entity=proposal.entity)
                    | Q(
                        entity__isnull=True,
                        entity_name__iexact=proposal.entity.name,
                    ),
                    pk=proposal.target_entry_id,
                    guide=proposal.guide,
                )
            except GuideEntry.DoesNotExist as exc:
                raise HttpError(409, "Proposal target entry is no longer available") from exc
            if entry.is_retired:
                raise HttpError(409, "Proposal target entry is already retired")
            if entry.revision != proposal.expected_revision:
                raise HttpError(409, "Guide entry revision is stale; review a new proposal")

            merged_evidence = list(entry.evidence)
            for item in proposal.evidence:
                if item not in merged_evidence:
                    merged_evidence.append(item)
            entry.evidence = merged_evidence
            update_fields = ["evidence", "revision", "updated_at"]
            if proposal.proposal_type == GuideProposal.ProposalType.UPDATE:
                proposed = proposal.proposed_entry.get("suitability")
                if not isinstance(proposed, str) or not proposed.strip():
                    raise HttpError(409, "Update proposal has no suitability text")
                # Merge, never overwrite: existing editorial text is preserved and
                # the proposed detail is appended once.
                current = entry.suitability.strip()
                if not current:
                    entry.suitability = proposed
                elif proposed not in current:
                    entry.suitability = f"{current}\n\n{proposed}"
                update_fields.append("suitability")
            elif proposal.proposal_type == GuideProposal.ProposalType.WARNING:
                warning = proposal.proposed_entry.get("warning")
                if not isinstance(warning, str) or not warning.strip():
                    raise HttpError(409, "Warning proposal has no warning text")
                if warning not in entry.caveats:
                    entry.caveats = [*entry.caveats, warning]
                warnings = list(entry.review_metadata.get("warnings", []))
                flagged = {
                    "type": "potentially_outdated",
                    "note": warning,
                    "evidence": proposal.evidence,
                }
                if flagged not in warnings:
                    warnings.append(flagged)
                entry.review_metadata = {
                    **entry.review_metadata,
                    "warnings": warnings,
                }
                update_fields.extend(["caveats", "review_metadata"])
            elif proposal.proposal_type == GuideProposal.ProposalType.RETIRE:
                entry.is_retired = True
                update_fields.append("is_retired")

            if entry.entity_id is None:
                entry.entity = proposal.entity
                update_fields.append("entity")
            entry.review_metadata = {
                **entry.review_metadata,
                "proposal_status": GuideProposal.Status.ACCEPTED,
                "accepted_proposal_id": proposal.pk,
            }
            if "review_metadata" not in update_fields:
                update_fields.append("review_metadata")
            entry.revision += 1
            entry.save(update_fields=update_fields)
            _record_revision(entry, request.user)

        proposal.status = GuideProposal.Status.ACCEPTED
        proposal.accepted_entry = entry
        proposal.save(update_fields=["status", "accepted_entry"])
    return entry


@router.post("/proposals/{proposal_id}/reject", response=GuideProposalOut)
def reject_proposal(request: HttpRequest, proposal_id: int):
    with transaction.atomic():
        try:
            proposal = GuideProposal.objects.select_for_update().get(
                pk=proposal_id,
                guide__owner=request.user,
            )
        except GuideProposal.DoesNotExist as exc:
            raise HttpError(404, "Guide proposal not found") from exc
        if proposal.status != GuideProposal.Status.PENDING:
            raise HttpError(409, "Guide proposal is no longer pending")
        proposal.status = GuideProposal.Status.REJECTED
        proposal.save(update_fields=["status"])
    return proposal


@router.get("/entries/{entry_id}/revisions", response=GuideRevisionList)
def entry_revisions(request: HttpRequest, entry_id: int):
    entry = _owned_entry(request, entry_id)
    return {"items": entry.revisions.select_related("changed_by").all()}
