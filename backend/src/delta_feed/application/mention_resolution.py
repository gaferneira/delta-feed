from django.db import transaction
from django.utils import timezone

from delta_feed.core.claim_fingerprint import normalize_name
from delta_feed.jobs.models import Job
from delta_feed.knowledge.models import Entity, ExtractedMention

MAX_CANDIDATES = 5


class MentionGroupNotFound(LookupError):
    """No pending mentions share the given normalized name and entity type."""


class InvalidMentionResolution(ValueError):
    """The resolve request is inconsistent with the group or its entity."""


def _same_type(left, right):
    return str(left).strip().casefold() == str(right).strip().casefold()


def _entity_names(entity):
    return {normalize_name(entity.name), *(normalize_name(alias) for alias in entity.aliases)}


def resolve_by_name(name, entity_type):
    """Return the one entity whose name or alias matches, else None.

    The type is ignored: models label one thing differently between articles
    ("software" in one, "practice" in the next), which split it into two entities.
    Several entities sharing the name still leave the mention pending.
    """
    target = normalize_name(name)
    matches = [entity for entity in Entity.objects.all() if target in _entity_names(entity)]
    return matches[0] if len(matches) == 1 else None


def candidate_entities(name, entity_type, limit=MAX_CANDIDATES):
    """Entities whose name contains or is contained by the name, closest length first."""
    target = normalize_name(name)
    if not target:
        return []
    scored = []
    for entity in Entity.objects.all():
        names = _entity_names(entity)
        if any(item and (target in item or item in target) for item in names):
            gap = min(abs(len(item) - len(target)) for item in names if item)
            scored.append((gap, entity.name, entity.pk, entity))
    scored.sort(key=lambda row: row[:3])
    return [row[3] for row in scored[:limit]]


def queue_mentions(analysis_run, mentions, claims):
    """Store every extracted mention; idempotent on (analysis_run, ref).

    Exactly one matching entity resolves a mention automatically; a group that
    was dismissed before is stored dismissed; everything else waits as pending.
    Returns the stored rows, including ones from an earlier attempt.
    """
    claims_by_ref = {}
    for claim in claims:
        claims_by_ref.setdefault(claim.get("entity_ref"), []).append(claim)
    stored = []
    with transaction.atomic():
        for mention in mentions:
            ref = mention["ref"]
            existing = ExtractedMention.objects.filter(analysis_run=analysis_run, ref=ref).first()
            if existing is not None:
                stored.append(existing)
                continue
            name = mention["name"]
            entity_type = str(mention["entity_type"]).strip()
            normalized = normalize_name(name)
            entity = resolve_by_name(name, entity_type)
            if entity is not None:
                status = ExtractedMention.Status.RESOLVED
            elif any(
                _same_type(row.entity_type, entity_type)
                for row in ExtractedMention.objects.filter(
                    normalized_name=normalized, status=ExtractedMention.Status.DISMISSED
                )
            ):
                status = ExtractedMention.Status.DISMISSED
            else:
                status = ExtractedMention.Status.PENDING
            stored.append(
                ExtractedMention.objects.create(
                    analysis_run=analysis_run,
                    source_article=analysis_run.source_article,
                    ref=ref,
                    name=name,
                    normalized_name=normalized,
                    entity_type=entity_type,
                    evidence=mention.get("evidence", []),
                    claims=claims_by_ref.get(ref, []),
                    status=status,
                    entity=entity,
                )
            )
    return stored


def resolve_group(normalized_name, entity_type, action, entity=None, new_entity=None):
    """Resolve every pending mention of a group; returns the resolved mentions."""
    with transaction.atomic():
        group = [
            mention
            for mention in ExtractedMention.objects.select_for_update().filter(
                normalized_name=normalized_name, status=ExtractedMention.Status.PENDING
            )
            if _same_type(mention.entity_type, entity_type)
        ]
        if not group:
            raise MentionGroupNotFound("No pending mentions for this group")
        now = timezone.now()
        if action == "dismiss":
            if entity is not None or new_entity is not None:
                raise InvalidMentionResolution("dismiss takes no entity")
            status, target = ExtractedMention.Status.DISMISSED, None
        elif action == "link":
            if entity is None or new_entity is not None:
                raise InvalidMentionResolution("link requires an existing entity only")
            status, target = ExtractedMention.Status.RESOLVED, entity
        elif action == "create":
            if entity is not None:
                raise InvalidMentionResolution("create does not take an existing entity")
            data = new_entity or {}
            target = Entity.objects.create(
                name=data.get("name") or group[0].name,
                type=data.get("entity_type") or group[0].entity_type,
                canonical_url=data.get("canonical_url"),
            )
            status = ExtractedMention.Status.RESOLVED
        else:
            raise InvalidMentionResolution("unknown action")

        if target is not None:
            known = _entity_names(target)
            aliases = list(target.aliases)
            for mention in group:
                normalized = normalize_name(mention.name)
                if normalized not in known:
                    known.add(normalized)
                    aliases.append(mention.name)
            if aliases != list(target.aliases):
                target.aliases = aliases
                target.save(update_fields=["aliases", "updated_at"])
        for mention in group:
            mention.status = status
            mention.entity = target
            mention.resolved_at = now
            mention.save(update_fields=["status", "entity", "resolved_at"])
        return group


def pending_mention_counts():
    """(groups, articles) still waiting for a decision; a group is name plus type."""
    pending = ExtractedMention.objects.filter(status=ExtractedMention.Status.PENDING)
    groups = {
        (name, (entity_type or "").strip().casefold())
        for name, entity_type in pending.values_list("normalized_name", "entity_type")
    }
    return len(groups), pending.values("source_article").distinct().count()


class NothingToUndo(LookupError):
    """The group has no decision that can be taken back."""


class AlreadyCompared(RuntimeError):
    """The decision already fed a comparison, so it cannot be taken back."""


COMPARE_GROUP_JOB_TYPE = "analysis.compare_group"


def undo_group(normalized_name, entity_type):
    """Return a decided group to pending; returns the number of mentions restored.

    Mentions matched automatically at ingestion are left alone: only decisions
    made by hand (resolved_at set) and dismissals are taken back.
    """
    with transaction.atomic():
        decided = [
            mention
            for mention in ExtractedMention.objects.select_for_update().filter(
                normalized_name=normalized_name,
                status__in=[ExtractedMention.Status.RESOLVED, ExtractedMention.Status.DISMISSED],
            )
            if _same_type(mention.entity_type, entity_type)
        ]
        targets = [
            mention
            for mention in decided
            if mention.status == ExtractedMention.Status.DISMISSED or mention.resolved_at is not None
        ]
        if not targets:
            raise NothingToUndo("nothing to undo")
        jobs = Job.objects.filter(
            type=COMPARE_GROUP_JOB_TYPE,
            payload__normalized_name=normalized_name,
            payload__entity_type=str(entity_type).strip().casefold(),
        )
        if any(mention.compared_at is not None for mention in targets) or jobs.filter(
            status=Job.Status.RUNNING
        ).exists():
            raise AlreadyCompared("already compared")
        jobs.filter(status=Job.Status.PENDING).delete()
        decided_at = min(
            (mention.resolved_at for mention in targets if mention.resolved_at is not None),
            default=None,
        )
        entities = {mention.entity for mention in targets if mention.entity is not None}
        for mention in targets:
            mention.status = ExtractedMention.Status.PENDING
            mention.entity = None
            mention.resolved_at = None
            mention.save(update_fields=["status", "entity", "resolved_at"])
        for entity in entities:
            aliases = [a for a in entity.aliases if normalize_name(a) != normalized_name]
            if aliases != list(entity.aliases):
                entity.aliases = aliases
                entity.save(update_fields=["aliases", "updated_at"])
            if (
                decided_at is not None
                and entity.created_at >= decided_at
                and not entity.claims.exists()
                and not entity.mentions.exists()
            ):
                entity.delete()
        return len(targets)
