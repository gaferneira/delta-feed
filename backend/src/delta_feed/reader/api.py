from datetime import datetime, timedelta
from typing import Literal

from django.conf import settings
from django.db.models import Count, Exists, F, OuterRef, Subquery
from django.db.models.functions import Coalesce, Substr
from django.http import HttpRequest
from django.utils import timezone
from ninja import Query, Router, Schema
from ninja.errors import HttpError

from delta_feed.analysis.models import AnalysisRun
from delta_feed.analysis.status import analysis_status, current_run
from delta_feed.application.mention_resolution import pending_mention_counts
from delta_feed.content.models import Article
from delta_feed.knowledge.models import Claim, Topic
from delta_feed.reader.models import ReadState, SaveState
from delta_feed.reader.today import select_today

router = Router(tags=["reader"])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
EXCERPT_LENGTH = 300
MAX_ENTITY_CHIPS = 3
TODAY_WINDOW = timedelta(hours=24)


class ReadInput(Schema):
    read: bool = True


class SaveInput(Schema):
    saved: bool = True


@router.post("/articles/{article_id}/read")
def mark_read(request: HttpRequest, article_id: int, payload: ReadInput):
    if not Article.objects.filter(pk=article_id).exists():
        raise HttpError(404, "Article not found")
    state, _ = ReadState.objects.update_or_create(
        user=request.user,
        article_id=article_id,
        defaults={"is_read": payload.read},
    )
    return {"article_id": article_id, "is_read": state.is_read}


@router.post("/articles/{article_id}/save")
def mark_saved(request: HttpRequest, article_id: int, payload: SaveInput):
    if not Article.objects.filter(pk=article_id).exists():
        raise HttpError(404, "Article not found")
    state, _ = SaveState.objects.update_or_create(
        user=request.user,
        article_id=article_id,
        defaults={"is_saved": payload.saved},
    )
    return {"article_id": article_id, "is_saved": state.is_saved}


class EntityRef(Schema):
    name: str
    type: str


class FeedItem(Schema):
    article_id: int
    url: str
    title: str
    excerpt: str
    revision_number: int
    is_read: bool
    is_saved: bool
    source_name: str | None
    is_backfill: bool
    published_at: datetime | None
    discovered_at: datetime
    # Extraction state of the current revision; unanalysed is shown, never hidden.
    analysis_status: Literal["unanalysed", "analysed", "failed"]
    # Titles of the topics the article's source belongs to; empty for manual submissions.
    topics: list[str]
    # The most-mentioned known entities of the current revision, at most MAX_ENTITY_CHIPS.
    entities: list[EntityRef]


class FeedPage(Schema):
    items: list[FeedItem]
    total: int
    limit: int
    offset: int
    has_more: bool
    # Today only: articles from the last 24 hours beyond the budget (still reachable).
    more_count: int = 0


def _topics_by_article(article_ids: list[int]) -> dict[int, list[str]]:
    """Topic titles per article, inherited from the article's source."""
    source_of = dict(
        Article.objects.filter(pk__in=article_ids).values_list("pk", "source_id")
    )
    titles: dict[int, list[str]] = {}
    for source_id, title in Topic.objects.filter(
        sources__in=set(source_of.values()) - {None}
    ).values_list("sources", "title"):
        titles.setdefault(source_id, []).append(title)
    return {pk: sorted(titles.get(source_id, [])) for pk, source_id in source_of.items()}


def _entities_by_article(article_ids: list[int]) -> dict[int, list[dict]]:
    """Top entities per article from its latest completed extraction, by claim count.

    Only entities that already exist: names still waiting for review have no claim yet.
    """
    rows = (
        Claim.objects.filter(
            source_article_id__in=article_ids,
            analysis_run_id=_latest_extract_run_id(
                "source_article_id", "source_article__current_version"
            ),
        )
        .values("source_article_id", "entity_id", "entity__name", "entity__type")
        .annotate(mentions=Count("id"))
        .order_by("source_article_id", "-mentions", "entity__name")
    )
    found: dict[int, list[dict]] = {pk: [] for pk in article_ids}
    for row in rows:
        chips = found[row["source_article_id"]]
        if len(chips) < MAX_ENTITY_CHIPS:
            chips.append({"name": row["entity__name"], "type": row["entity__type"]})
    return found


@router.get("/feed", response=FeedPage)
def feed(
    request: HttpRequest,
    view: Literal["today", "backfill", "all"] = "today",
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
    more: bool = False,
):
    """Paginated feed. Quietly backfilled history stays out of Today by default.

    Today is current articles discovered in the last 24 hours, cut to a budget with a
    per-source cap. ``more=true`` returns the rest of that day instead of the budget.
    """
    articles = Article.objects.all()
    more_count = 0
    if view == "today":
        recent = articles.filter(
            is_backfill=False, created_at__gte=timezone.now() - TODAY_WINDOW
        ).order_by("-created_at", "-id")
        # A manual submission is deliberate attention: it never competes for a source cap.
        candidates = [
            (pk, source_id if source_id is not None else f"manual:{pk}")
            for pk, source_id in recent.values_list("pk", "source_id")
        ]
        shown, overflow = select_today(
            candidates,
            budget=settings.TODAY_BUDGET,
            per_source_cap=settings.TODAY_PER_SOURCE_CAP,
        )
        more_count = len(overflow)
        selected = overflow if more else shown
        articles = articles.filter(pk__in=selected)
    elif view == "backfill":
        articles = articles.filter(is_backfill=True)
    total = articles.count()
    ordering = ("-created_at", "-id") if view == "today" else ("-published_at", "-id")
    rows = list(
        articles.annotate(
            excerpt=Substr("body", 1, EXCERPT_LENGTH),
            source_name=F("source__name"),
            published_at=Coalesce("source_published_at", "created_at"),
            is_read=Exists(
                ReadState.objects.filter(
                    user=request.user, article=OuterRef("pk"), is_read=True
                )
            ),
            is_saved=Exists(
                SaveState.objects.filter(
                    user=request.user, article=OuterRef("pk"), is_saved=True
                )
            ),
            is_analysed=Exists(current_run(status=AnalysisRun.Status.COMPLETED)),
            is_analysis_failed=Exists(
                current_run(failure_reason=AnalysisRun.FailureReason.INVALID_OUTPUT)
            ),
        )
        .order_by(*ordering)
        .values(
            "id", "url", "title", "excerpt", "current_version", "is_read",
            "is_saved", "source_name", "is_backfill", "published_at", "created_at",
            "is_analysed", "is_analysis_failed",
        )[offset : offset + limit]
    )
    topics = _topics_by_article([row["id"] for row in rows])
    entities = _entities_by_article([row["id"] for row in rows])
    return {
        "items": [
            {
                "article_id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "excerpt": row["excerpt"],
                "revision_number": row["current_version"],
                "is_read": row["is_read"],
                "is_saved": row["is_saved"],
                "source_name": row["source_name"],
                "is_backfill": row["is_backfill"],
                "published_at": row["published_at"],
                "discovered_at": row["created_at"],
                "analysis_status": analysis_status(row),
                "topics": topics.get(row["id"], []),
                "entities": entities.get(row["id"], []),
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "more_count": more_count,
    }


@router.get("/saved", response=FeedPage)
def saved(
    request: HttpRequest,
    status: Literal["all", "unread", "read"] = "all",
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """The reading queue: articles the user saved, most recently saved first.

    ``status`` narrows it to the ones not read yet or already read.
    """
    mine = SaveState.objects.filter(
        user=request.user, article=OuterRef("pk"), is_saved=True
    )
    was_read = ReadState.objects.filter(
        user=request.user, article=OuterRef("pk"), is_read=True
    )
    articles = Article.objects.filter(Exists(mine))
    if status == "unread":
        articles = articles.exclude(Exists(was_read))
    elif status == "read":
        articles = articles.filter(Exists(was_read))
    total = articles.count()
    rows = list(
        articles.annotate(
            excerpt=Substr("body", 1, EXCERPT_LENGTH),
            source_name=F("source__name"),
            published_at=Coalesce("source_published_at", "created_at"),
            saved_at=Subquery(mine.values("updated_at")[:1]),
            is_read=Exists(was_read),
            is_saved=Exists(mine),
            is_analysed=Exists(current_run(status=AnalysisRun.Status.COMPLETED)),
            is_analysis_failed=Exists(
                current_run(failure_reason=AnalysisRun.FailureReason.INVALID_OUTPUT)
            ),
        )
        .order_by("-saved_at", "-id")
        .values(
            "id", "url", "title", "excerpt", "current_version", "is_read",
            "is_saved", "source_name", "is_backfill", "published_at", "created_at",
            "is_analysed", "is_analysis_failed",
        )[offset : offset + limit]
    )
    topics = _topics_by_article([row["id"] for row in rows])
    entities = _entities_by_article([row["id"] for row in rows])
    return {
        "items": [
            {
                "article_id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "excerpt": row["excerpt"],
                "revision_number": row["current_version"],
                "is_read": row["is_read"],
                "is_saved": row["is_saved"],
                "source_name": row["source_name"],
                "is_backfill": row["is_backfill"],
                "published_at": row["published_at"],
                "discovered_at": row["created_at"],
                "analysis_status": analysis_status(row),
                "topics": topics.get(row["id"], []),
                "entities": entities.get(row["id"], []),
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "more_count": 0,
    }


DELTA_CLASSIFICATIONS = (
    Claim.Classification.NEW,
    Claim.Classification.REFINEMENT,
    Claim.Classification.CONTRADICTION,
    Claim.Classification.UNSURE,
)


class DeltaClaim(Schema):
    id: int
    entity_name: str
    predicate: str | None
    value: str | None
    claim_text: str
    classification: Literal["new", "refinement", "contradiction", "unsure"]
    first_sighting: bool
    evidence_text: str
    matched_claim_text: str | None


class DeltaItem(FeedItem):
    claims: list[DeltaClaim]
    also_covered_by: int


class PendingMentions(Schema):
    groups: int
    articles: int


class DeltaPage(Schema):
    items: list[DeltaItem]
    total: int
    limit: int
    offset: int
    has_more: bool
    pending_mentions: PendingMentions


def _latest_extract_run_id(article_ref: str, version_ref: str):
    """Id of the latest completed extraction run of an article's current revision."""
    return Subquery(
        AnalysisRun.objects.filter(
            source_article=OuterRef(article_ref),
            article_revision__version=OuterRef(version_ref),
            kind=AnalysisRun.Kind.EXTRACT,
            status=AnalysisRun.Status.COMPLETED,
        )
        .order_by("-id")
        .values("id")[:1]
    )


@router.get("/delta", response=DeltaPage)
def delta(
    request: HttpRequest,
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Articles carrying claims that are not duplicates of the baseline, newest first.

    Articles the user already read or saved are handled and leave the page.

    Quietly backfilled history seeds the baseline but never produces cards.
    """
    claims = Claim.objects.filter(
        source_article=OuterRef("pk"),
        classification__in=DELTA_CLASSIFICATIONS,
        analysis_run_id=_latest_extract_run_id(
            "source_article_id", "source_article__current_version"
        ),
    )
    handled = Exists(
        ReadState.objects.filter(user=request.user, article=OuterRef("pk"), is_read=True)
    ) | Exists(
        SaveState.objects.filter(user=request.user, article=OuterRef("pk"), is_saved=True)
    )
    articles = (
        Article.objects.filter(is_backfill=False)
        .filter(Exists(claims))
        .exclude(handled)
    )
    total = articles.count()
    rows = list(
        articles.annotate(
            excerpt=Substr("body", 1, EXCERPT_LENGTH),
            source_name=F("source__name"),
            published_at=Coalesce("source_published_at", "created_at"),
            is_read=Exists(
                ReadState.objects.filter(
                    user=request.user, article=OuterRef("pk"), is_read=True
                )
            ),
            is_saved=Exists(
                SaveState.objects.filter(
                    user=request.user, article=OuterRef("pk"), is_saved=True
                )
            ),
            is_analysed=Exists(current_run(status=AnalysisRun.Status.COMPLETED)),
            is_analysis_failed=Exists(
                current_run(failure_reason=AnalysisRun.FailureReason.INVALID_OUTPUT)
            ),
        )
        .order_by("-published_at", "-id")
        .values(
            "id", "url", "title", "excerpt", "current_version", "is_read",
            "is_saved", "source_name", "is_backfill", "published_at", "created_at",
            "is_analysed", "is_analysis_failed",
        )[offset : offset + limit]
    )
    article_ids = [row["id"] for row in rows]
    topics = _topics_by_article(article_ids)
    entities = _entities_by_article(article_ids)

    claims_by_article: dict[int, list[dict]] = {pk: [] for pk in article_ids}
    claim_rows = (
        Claim.objects.filter(
            source_article_id__in=article_ids,
            classification__in=DELTA_CLASSIFICATIONS,
            analysis_run_id=_latest_extract_run_id(
                "source_article_id", "source_article__current_version"
            ),
        )
        .select_related("entity", "matched_claim")
        .order_by("id")
    )
    for claim in claim_rows:
        claims_by_article[claim.source_article_id].append(
            {
                "id": claim.pk,
                "entity_name": claim.entity.name,
                "predicate": claim.predicate,
                "value": claim.value,
                "claim_text": claim.claim_text,
                "classification": claim.classification,
                "first_sighting": claim.comparison_method
                == Claim.ComparisonMethod.FIRST_SIGHTING,
                "evidence_text": claim.evidence_text,
                "matched_claim_text": claim.matched_claim.claim_text
                if claim.matched_claim
                else None,
            }
        )

    # Duplicate claims of other articles that point at a displayed claim.
    displayed = {c["id"]: pk for pk, cs in claims_by_article.items() for c in cs}
    covering: dict[int, set[int]] = {pk: set() for pk in article_ids}
    for matched_id, duplicate_article_id in Claim.objects.filter(
        classification=Claim.Classification.DUPLICATE,
        matched_claim_id__in=list(displayed),
    ).values_list("matched_claim_id", "source_article_id"):
        owner = displayed[matched_id]
        if duplicate_article_id != owner:
            covering[owner].add(duplicate_article_id)

    pending_groups, pending_articles = pending_mention_counts()

    return {
        "items": [
            {
                "article_id": row["id"],
                "url": row["url"],
                "title": row["title"],
                "excerpt": row["excerpt"],
                "revision_number": row["current_version"],
                "is_read": row["is_read"],
                "is_saved": row["is_saved"],
                "source_name": row["source_name"],
                "is_backfill": row["is_backfill"],
                "published_at": row["published_at"],
                "discovered_at": row["created_at"],
                "analysis_status": analysis_status(row),
                "topics": topics.get(row["id"], []),
                "entities": entities.get(row["id"], []),
                "claims": claims_by_article[row["id"]],
                "also_covered_by": len(covering[row["id"]]),
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "pending_mentions": {"groups": pending_groups, "articles": pending_articles},
    }
