from datetime import datetime
from typing import Literal

from django.db.models import Exists, F, OuterRef
from django.db.models.functions import Coalesce, Substr
from django.http import HttpRequest
from ninja import Query, Router, Schema
from ninja.errors import HttpError

from delta_feed.content.models import Article
from delta_feed.reader.models import ReadState, SaveState

router = Router(tags=["reader"])

DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 100
EXCERPT_LENGTH = 300


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


class FeedPage(Schema):
    items: list[FeedItem]
    total: int
    limit: int
    offset: int
    has_more: bool


@router.get("/feed", response=FeedPage)
def feed(
    request: HttpRequest,
    view: Literal["today", "backfill", "all"] = "today",
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(0, ge=0),
):
    """Paginated feed. Quietly backfilled history stays out of Today by default."""
    articles = Article.objects.all()
    if view == "today":
        articles = articles.filter(is_backfill=False)
    elif view == "backfill":
        articles = articles.filter(is_backfill=True)
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
        )
        .order_by("-published_at", "-id")
        .values(
            "id", "url", "title", "excerpt", "current_version", "is_read",
            "is_saved", "source_name", "is_backfill", "published_at",
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
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(rows) < total,
    }
