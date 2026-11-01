import hashlib

from django.db import transaction
from django.db.models import F
from ninja import Field, Router, Schema
from ninja.responses import Status
from pydantic import field_validator

from delta_feed.content.models import Article, ArticleRevision
from delta_feed.content.urls import safe_http_url

router = Router(tags=["content"])


class ArticleSubmission(Schema):
    url: str = Field(min_length=8, max_length=2048)
    title: str = Field(min_length=1, max_length=500)
    body: str = Field(min_length=1, max_length=300_000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if safe_http_url(value) != value:
            raise ValueError("url must be an absolute HTTP(S) URL without credentials")
        return value


def article_content_hash(title: str, body: str) -> str:
    """Fingerprint a supplied snapshot without conflating title/body boundaries."""
    return hashlib.sha256(f"{title}\0{body}".encode()).hexdigest()


@transaction.atomic
def submit_article(*, user, url: str, title: str, body: str):
    # Article identity is URL-scoped: a URL already ingested from a feed is the same
    # article, so a manual submission appends a revision to it rather than creating
    # a parallel manual row. Prefer the manual row if both exist.
    article_created = False
    existing = (
        Article.objects.select_for_update()
        .filter(url=url)
        .order_by(F("source_id").asc(nulls_first=True), "id")
        .first()
    )
    if existing is None:
        article, article_created = Article.objects.get_or_create(
            url=url,
            source__isnull=True,
            defaults={"title": title, "body": body},
        )
    else:
        article = existing
    article = Article.objects.select_for_update().get(pk=article.pk)
    if article.is_backfill:
        # An explicit submission is deliberate attention, not a quiet import.
        article.is_backfill = False
        article.save(update_fields=["is_backfill", "updated_at"])
    fingerprint = article_content_hash(title, body)
    latest = article.revisions.order_by("-version").first()

    if latest is not None and latest.content_hash == fingerprint:
        return article, latest.version, article_created

    version = 1 if latest is None else latest.version + 1
    ArticleRevision.objects.create(
        article=article,
        version=version,
        title=title,
        body=body,
        content_hash=fingerprint,
        submitted_by=user,
    )
    article.title = title
    article.body = body
    article.current_version = version
    article.save(update_fields=["title", "body", "current_version", "updated_at"])
    return article, version, article_created


class ArticleSubmissionResult(Schema):
    article_id: int
    revision_number: int
    created: bool


@router.post("/articles", response={200: ArticleSubmissionResult, 201: ArticleSubmissionResult})
def submit_article_endpoint(request, payload: ArticleSubmission):
    article, version, created = submit_article(
        user=request.user,
        url=payload.url,
        title=payload.title,
        body=payload.body,
    )
    return Status(201 if created else 200, {
        "article_id": article.pk,
        "revision_number": version,
        "created": created,
    })
