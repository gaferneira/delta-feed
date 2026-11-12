import math
import re
from datetime import datetime
from typing import Any, Literal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.http import HttpRequest
from ninja import Field, Router, Schema
from ninja.errors import HttpError
from ninja.responses import Status
from pydantic import field_validator, model_validator

from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.use_cases import enqueue_compare_group
from delta_feed.application.entity_matching import match_or_suggest_entities
from delta_feed.application.mention_resolution import (
    AlreadyCompared,
    InvalidMentionResolution,
    MentionGroupNotFound,
    NothingToUndo,
    candidate_entities,
    pending_mention_counts,
    resolve_group,
    undo_group,
)
from delta_feed.core.claim_fingerprint import normalize_name
from delta_feed.knowledge.models import Claim, Entity, ExtractedMention
from delta_feed.knowledge.use_cases import AnalysisRunNotCompleted, record_claim

router = Router(tags=["knowledge"])
_IDENTIFIER_KIND = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_RESERVED_IDENTIFIER_KINDS = {"canonical_url", "slug"}


def _validate_identifiers(value: dict[str, str]) -> dict[str, str]:
    for kind, identifier in value.items():
        if not _IDENTIFIER_KIND.fullmatch(kind) or not identifier:
            raise ValueError("Identifiers require a valid type and non-empty value")
    return value


class EntityCreate(Schema):
    name: str = Field(min_length=1, max_length=250)
    type: str = Field(min_length=1, max_length=80)
    canonical_url: str | None = Field(default=None, max_length=2048)
    slug: str | None = Field(default=None, max_length=250)
    identifiers: dict[str, str] = Field(default_factory=dict)
    aliases: list[str] = Field(default_factory=list)

    @field_validator("identifiers")
    @classmethod
    def validate_identifiers(cls, value: dict[str, str]) -> dict[str, str]:
        _validate_identifiers(value)
        if _RESERVED_IDENTIFIER_KINDS.intersection(value):
            raise ValueError("canonical_url and slug must use their dedicated fields")
        return value


class EntityPatch(Schema):
    name: str | None = Field(default=None, min_length=1, max_length=250)
    type: str | None = Field(default=None, min_length=1, max_length=80)
    canonical_url: str | None = Field(default=None, max_length=2048)
    slug: str | None = Field(default=None, max_length=250)
    identifiers: dict[str, str] | None = None
    aliases: list[str] | None = None

    @field_validator("identifiers")
    @classmethod
    def validate_identifiers(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is not None:
            _validate_identifiers(value)
            if _RESERVED_IDENTIFIER_KINDS.intersection(value):
                raise ValueError("canonical_url and slug must use their dedicated fields")
        return value


class EntityOut(Schema):
    id: int
    name: str
    type: str
    canonical_url: str | None
    slug: str | None
    identifiers: dict[str, str]
    aliases: list[str]
    created_at: Any
    updated_at: Any


class EntityList(Schema):
    items: list[EntityOut]


class EntityMatchInput(Schema):
    identifiers: dict[str, str] = Field(default_factory=dict)
    embedding: list[float] | None = None
    model_version: str | None = Field(default=None, min_length=1, max_length=120)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("identifiers")
    @classmethod
    def validate_identifiers(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_identifiers(value)

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, value: list[float] | None) -> list[float] | None:
        if value is not None:
            if not value or any(not math.isfinite(item) for item in value):
                raise ValueError("embedding must contain finite values")
            if not any(item != 0 for item in value):
                raise ValueError("embedding must not be a zero vector")
        return value

    @model_validator(mode="after")
    def embedding_requires_model_version(self):
        if self.embedding is not None and self.model_version is None:
            raise ValueError("model_version is required when an embedding is provided")
        return self


class EntityCandidateSearchInput(Schema):
    identifiers: dict[str, str] = Field(default_factory=dict)
    embedding: list[float]
    model_version: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=10, ge=1, le=50)

    @field_validator("identifiers")
    @classmethod
    def validate_identifiers(cls, value: dict[str, str]) -> dict[str, str]:
        return _validate_identifiers(value)

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, value: list[float]) -> list[float]:
        if not value or any(not math.isfinite(item) for item in value):
            raise ValueError("embedding must contain finite values")
        if not any(item != 0 for item in value):
            raise ValueError("embedding must not be a zero vector")
        return value


class EntityCandidateOut(Schema):
    entity: EntityOut
    similarity: float


class EntityMatchOutput(Schema):
    entity: EntityOut | None
    candidates: list[EntityCandidateOut] = Field(default_factory=list)


class EntityCandidatesOutput(Schema):
    candidates: list[EntityCandidateOut]
    auto_merged: bool = False


@router.get("/entities", response=EntityList)
def list_entities(request: HttpRequest):
    return {"items": Entity.objects.all()}


@router.post("/entities", response={201: EntityOut})
def create_entity(request: HttpRequest, payload: EntityCreate):
    return Status(201, Entity.objects.create(**payload.model_dump()))


@router.post("/entities/match", response=EntityMatchOutput)
def match_entity(request: HttpRequest, payload: EntityMatchInput):
    entity, candidates = match_or_suggest_entities(
        payload.identifiers,
        embedding=payload.embedding,
        model_version=payload.model_version,
        limit=payload.limit,
    )
    return {"entity": entity, "candidates": candidates}


@router.post("/entities/candidates", response=EntityCandidatesOutput)
def entity_candidates(request: HttpRequest, payload: EntityCandidateSearchInput):
    _, candidates = match_or_suggest_entities(
        payload.identifiers,
        embedding=payload.embedding,
        model_version=payload.model_version,
        limit=payload.limit,
    )
    return {"candidates": candidates, "auto_merged": False}


@router.get("/entities/{entity_id}", response=EntityOut)
def get_entity(request: HttpRequest, entity_id: int):
    try:
        return Entity.objects.get(pk=entity_id)
    except Entity.DoesNotExist as exc:
        raise HttpError(404, "Entity not found") from exc


@router.patch("/entities/{entity_id}", response=EntityOut)
def update_entity(request: HttpRequest, entity_id: int, payload: EntityPatch):
    try:
        entity = Entity.objects.get(pk=entity_id)
    except Entity.DoesNotExist as exc:
        raise HttpError(404, "Entity not found") from exc
    values = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not values:
        raise HttpError(422, "At least one entity field must be provided")
    for field, value in values.items():
        setattr(entity, field, value)
    entity.save(update_fields=[*values, "updated_at"])
    return entity


@router.delete("/entities/{entity_id}", response={204: None})
def delete_entity(request: HttpRequest, entity_id: int):
    try:
        deleted, _ = Entity.objects.filter(pk=entity_id).delete()
    except ProtectedError as exc:
        # Claims are append-only evidence and mentions reference the entity; either
        # blocks deletion.
        raise HttpError(
            409, "Entity has recorded claims or mentions and cannot be deleted"
        ) from exc
    if not deleted:
        raise HttpError(404, "Entity not found")
    return Status(204, None)


class ClaimEvidenceInput(Schema):
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_span(self):
        if self.end <= self.start:
            raise ValueError("evidence end must be greater than start")
        return self


class ClaimCreate(Schema):
    entity_id: int
    analysis_run_id: int
    claim_text: str = Field(min_length=1)
    version: str | None = Field(default=None, max_length=120)
    platform: str | None = Field(default=None, max_length=120)
    availability: str | None = Field(default=None, max_length=120)
    evidence: ClaimEvidenceInput
    observed_at: datetime | None = None


class ClaimSourceOut(Schema):
    id: int
    title: str
    url: str
    source_name: str | None


class ClaimOut(Schema):
    id: int
    entity_id: int
    version: str | None
    platform: str | None
    availability: str | None
    claim_text: str
    source_article: ClaimSourceOut
    evidence_start: int
    evidence_end: int
    evidence_text: str
    observed_at: datetime
    analysis_run_id: int
    article_revision_id: int | None
    revision_number: int | None
    classification: str
    supersedes_id: int | None
    superseded_by_ids: list[int]
    created_at: datetime


class ClaimList(Schema):
    items: list[ClaimOut]


def _claim_output(claim, superseded_by_ids=None):
    source = claim.source_article
    return {
        "id": claim.pk,
        "entity_id": claim.entity_id,
        "version": claim.version,
        "platform": claim.platform,
        "availability": claim.availability,
        "claim_text": claim.claim_text,
        "source_article": {
            "id": source.pk,
            "title": source.title,
            "url": source.url,
            "source_name": source.source.name if source.source_id else None,
        },
        "evidence_start": claim.evidence_start,
        "evidence_end": claim.evidence_end,
        "evidence_text": claim.evidence_text,
        "observed_at": claim.observed_at,
        "analysis_run_id": claim.analysis_run_id,
        "article_revision_id": claim.analysis_run.article_revision_id,
        "revision_number": (
            claim.analysis_run.article_revision.version
            if claim.analysis_run.article_revision_id
            else None
        ),
        "classification": claim.classification,
        "supersedes_id": claim.supersedes_id,
        "superseded_by_ids": superseded_by_ids or [],
        "created_at": claim.created_at,
    }


@router.post("/claims", response={201: ClaimOut})
def create_claim(request: HttpRequest, payload: ClaimCreate):
    try:
        entity = Entity.objects.get(pk=payload.entity_id)
    except Entity.DoesNotExist as exc:
        raise HttpError(404, "Entity not found") from exc
    try:
        analysis_run = AnalysisRun.objects.select_related(
            "source_article", "article_revision"
        ).get(
            pk=payload.analysis_run_id
        )
    except AnalysisRun.DoesNotExist as exc:
        raise HttpError(404, "Analysis run not found") from exc

    try:
        claim = record_claim(
            entity,
            {
                "claim_text": payload.claim_text,
                "version": payload.version,
                "platform": payload.platform,
                "availability": payload.availability,
                "evidence_start": payload.evidence.start,
                "evidence_end": payload.evidence.end,
                "evidence_text": payload.evidence.quote,
                "observed_at": payload.observed_at,
            },
            analysis_run,
        )
    except AnalysisRunNotCompleted as exc:
        raise HttpError(409, str(exc)) from exc
    except ValueError as exc:
        raise HttpError(422, str(exc)) from exc
    return Status(201, _claim_output(claim))


@router.get("/entities/{entity_id}/claims", response=ClaimList)
def list_entity_claims(request: HttpRequest, entity_id: int):
    if not Entity.objects.filter(pk=entity_id).exists():
        raise HttpError(404, "Entity not found")
    claims = list(
        Claim.objects.filter(entity_id=entity_id)
        .select_related(
            "source_article",
            "source_article__source",
            "analysis_run",
            "analysis_run__article_revision",
        )
        .order_by("-observed_at", "-id")
    )
    superseded_by = {}
    for claim in claims:
        if claim.supersedes_id is not None:
            superseded_by.setdefault(claim.supersedes_id, []).append(claim.pk)
    return {
        "items": [
            _claim_output(claim, superseded_by.get(claim.pk, [])) for claim in claims
        ]
    }


class MentionCandidateOut(Schema):
    entity_id: int
    name: str
    type: str


class MentionArticleOut(Schema):
    article_id: int
    title: str
    url: str


class MentionGroupOut(Schema):
    normalized_name: str
    name_samples: list[str]
    entity_type: str
    count: int
    article_titles: list[str]
    articles: list[MentionArticleOut]
    article_count: int
    claim_count: int
    evidence_sample: str
    candidates: list[MentionCandidateOut]
    entity_id: int | None
    entity_name: str | None
    decided_at: datetime | None
    auto_matched: bool


class MentionGroupList(Schema):
    items: list[MentionGroupOut]


class MentionSummaryOut(Schema):
    pending_groups: int
    pending_articles: int


class NewEntityIn(Schema):
    name: str = Field(min_length=1, max_length=250)
    entity_type: str = Field(min_length=1, max_length=80)
    canonical_url: str | None = Field(default=None, max_length=2048)


class MentionResolveIn(Schema):
    normalized_name: str = Field(min_length=1, max_length=250)
    entity_type: str = Field(min_length=1, max_length=80)
    action: Literal["link", "create", "dismiss"]
    entity_id: int | None = None
    new_entity: NewEntityIn | None = None


class MentionResolveOut(Schema):
    resolved_mentions: int
    jobs_enqueued: int
    entity_id: int | None
    entity_name: str | None
    undo_seconds: int | None


class MentionResolveBatchIn(Schema):
    items: list[MentionResolveIn] = Field(min_length=1, max_length=50)


class MentionResolveItemOut(Schema):
    normalized_name: str
    entity_type: str
    ok: bool
    resolved_mentions: int
    jobs_enqueued: int
    entity_id: int | None
    entity_name: str | None
    undo_seconds: int | None
    error: str | None


class MentionResolveBatchOut(Schema):
    results: list[MentionResolveItemOut]


class MentionGroupRef(Schema):
    normalized_name: str = Field(min_length=1, max_length=250)
    entity_type: str = Field(min_length=1, max_length=80)


class MentionUndoIn(Schema):
    groups: list[MentionGroupRef] = Field(min_length=1, max_length=50)


class MentionUndoItemOut(Schema):
    normalized_name: str
    entity_type: str
    ok: bool
    restored_mentions: int
    error: str | None


class MentionUndoOut(Schema):
    results: list[MentionUndoItemOut]


@router.get("/mentions", response=MentionGroupList)
def list_mentions(request: HttpRequest, status: Literal["pending", "resolved", "dismissed"] = "pending"):
    groups: dict[tuple[str, str], list[ExtractedMention]] = {}
    mentions = ExtractedMention.objects.filter(status=status).select_related(
        "source_article", "entity"
    )
    for mention in mentions.order_by("id"):
        key = (mention.normalized_name, mention.entity_type.strip().casefold())
        groups.setdefault(key, []).append(mention)
    items = []
    for (normalized_name, _), members in groups.items():
        first = members[0]
        names = list(dict.fromkeys(mention.name for mention in members))[:3]
        titles = list(dict.fromkeys(mention.source_article.title for mention in members))[:3]
        articles = {}
        for mention in members:
            article = mention.source_article
            articles.setdefault(
                article.pk, {"article_id": article.pk, "title": article.title, "url": article.url}
            )
        quotes = first.evidence[0].get("quote", "") if first.evidence else ""
        decided = [m for m in members if m.resolved_at is not None]
        entity = None
        if status == ExtractedMention.Status.RESOLVED:
            by_decision = max(decided, key=lambda m: m.resolved_at) if decided else None
            entity = (by_decision or first).entity
        items.append(
            {
                "normalized_name": normalized_name,
                "name_samples": names,
                "entity_type": first.entity_type,
                "count": len(members),
                "article_titles": titles,
                "articles": list(articles.values())[:3],
                "article_count": len(articles),
                "claim_count": sum(len(mention.claims) for mention in members),
                "evidence_sample": quotes[:300],
                "candidates": [
                    {"entity_id": entity.pk, "name": entity.name, "type": entity.type}
                    for entity in candidate_entities(normalized_name, first.entity_type)
                ],
                "entity_id": entity.pk if entity else None,
                "entity_name": entity.name if entity else None,
                "decided_at": max((m.resolved_at for m in decided), default=None),
                "auto_matched": status == ExtractedMention.Status.RESOLVED and not decided,
            }
        )
    items.sort(key=lambda item: (-item["count"], item["normalized_name"]))
    return {"items": items}


@router.get("/mentions/summary", response=MentionSummaryOut)
def mentions_summary(request: HttpRequest):
    groups, articles = pending_mention_counts()
    return {"pending_groups": groups, "pending_articles": articles}


class ResolutionRejected(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _apply_resolution(payload: MentionResolveIn) -> dict:
    """One decision, in its own transaction; raises ResolutionRejected on refusal."""
    entity = None
    if payload.action == "link":
        if payload.entity_id is None:
            raise ResolutionRejected(422, "link requires entity_id")
        try:
            entity = Entity.objects.get(pk=payload.entity_id)
        except Entity.DoesNotExist as exc:
            raise ResolutionRejected(422, "Entity not found") from exc
    elif payload.entity_id is not None:
        raise ResolutionRejected(422, "entity_id is only valid with link")
    if payload.action != "create" and payload.new_entity is not None:
        raise ResolutionRejected(422, "new_entity is only valid with create")
    undo_seconds = settings.MENTION_UNDO_SECONDS if payload.action != "dismiss" else None
    try:
        with transaction.atomic():
            resolved = resolve_group(
                normalize_name(payload.normalized_name),
                payload.entity_type,
                payload.action,
                entity=entity,
                new_entity=payload.new_entity.model_dump() if payload.new_entity else None,
            )
    except MentionGroupNotFound as exc:
        raise ResolutionRejected(404, str(exc)) from exc
    except (InvalidMentionResolution, IntegrityError) as exc:
        raise ResolutionRejected(422, str(exc)) from exc
    jobs_enqueued = 0
    if payload.action != "dismiss":
        # One job per analysis run: each compares that run's claims for the group.
        run_ids = list(dict.fromkeys(mention.analysis_run_id for mention in resolved))
        for run_id in run_ids:
            job = enqueue_compare_group(
                normalize_name(payload.normalized_name),
                payload.entity_type,
                run_id,
                delay_seconds=undo_seconds or 0,
            )
            jobs_enqueued += job is not None
    target = resolved[0].entity
    return {
        "resolved_mentions": len(resolved),
        "jobs_enqueued": jobs_enqueued,
        "entity_id": target.pk if target else None,
        "entity_name": target.name if target else None,
        "undo_seconds": undo_seconds,
    }


@router.post("/mentions/resolve", response=MentionResolveOut)
def resolve_mentions(request: HttpRequest, payload: MentionResolveIn):
    try:
        return _apply_resolution(payload)
    except ResolutionRejected as exc:
        raise HttpError(exc.status_code, str(exc)) from exc


@router.post("/mentions/resolve-batch", response=MentionResolveBatchOut)
def resolve_mentions_batch(request: HttpRequest, payload: MentionResolveBatchIn):
    results = []
    for item in payload.items:
        base = {"normalized_name": item.normalized_name, "entity_type": item.entity_type}
        try:
            outcome = _apply_resolution(item)
        except ResolutionRejected as exc:
            results.append(
                {
                    **base,
                    "ok": False,
                    "resolved_mentions": 0,
                    "jobs_enqueued": 0,
                    "entity_id": None,
                    "entity_name": None,
                    "undo_seconds": None,
                    "error": str(exc),
                }
            )
        else:
            results.append({**base, "ok": True, "error": None, **outcome})
    return {"results": results}


@router.post("/mentions/undo", response=MentionUndoOut)
def undo_mentions(request: HttpRequest, payload: MentionUndoIn):
    results = []
    for ref in payload.groups:
        base = {"normalized_name": ref.normalized_name, "entity_type": ref.entity_type}
        try:
            restored = undo_group(normalize_name(ref.normalized_name), ref.entity_type)
        except (NothingToUndo, AlreadyCompared) as exc:
            results.append({**base, "ok": False, "restored_mentions": 0, "error": str(exc)})
        else:
            results.append({**base, "ok": True, "restored_mentions": restored, "error": None})
    return {"results": results}
