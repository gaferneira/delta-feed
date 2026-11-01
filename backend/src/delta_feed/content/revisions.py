from django.db import transaction

from delta_feed.content.api import article_content_hash
from delta_feed.content.models import Article, ArticleRevision


@transaction.atomic
def current_revision(article: Article) -> ArticleRevision:
    """Return the revision matching the article's current snapshot.

    Articles written before revisions existed get an append-only snapshot of
    their current text so analysis can reference exact, immutable content.
    """
    article = Article.objects.select_for_update().get(pk=article.pk)
    revision = article.revisions.filter(version=article.current_version).first()
    if revision is None:
        latest = article.revisions.order_by("-version").first()
        version = article.current_version if latest is None else latest.version + 1
        revision = ArticleRevision.objects.create(
            article=article,
            version=version,
            title=article.title,
            body=article.body,
            content_hash=article_content_hash(article.title, article.body),
            source_published_at=article.source_published_at,
            fetched_at=article.fetched_at,
        )
        if version != article.current_version:
            Article.objects.filter(pk=article.pk).update(current_version=version)
    return revision
