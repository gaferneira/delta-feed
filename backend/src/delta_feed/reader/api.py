from datetime import datetime, timedelta
from typing import Literal

from django.conf import settings
from django.db.models import Exists, F, OuterRef
from django.db.models.functions import Coalesce, Substr
from django.http import HttpRequest
from django.utils import timezone
from ninja import Query, Router, Schema
from ninja.errors import HttpError

from delta_feed.content.models import Article
from delta_feed.reader.models import ReadState, SaveState
from delta_feed.reader.today import select_today

router = Router(tags=["reader"])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
EXCERPT_LENGTH = 300
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


class FeedPage(Schema):
    items: list[FeedItem]
    total: int
    limit: int
    offset: int
    has_more: bool
    # Today only: articles from the last 24 hours beyond the budget (still reachable).
    more_count: int = 0


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
        )
        .order_by(*ordering)
        .values(
            "id", "url", "title", "excerpt", "current_version", "is_read",
            "is_saved", "source_name", "is_backfill", "published_at", "created_at",
        )[offset : offset + limit]
    )
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
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
        "more_count": more_count,
    }
