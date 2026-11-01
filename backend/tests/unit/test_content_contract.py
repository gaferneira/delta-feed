import pytest
from pydantic import ValidationError

from delta_feed.content.api import ArticleSubmission, article_content_hash


def test_content_hash_distinguishes_title_and_body_boundaries():
    assert article_content_hash("A", "BC") != article_content_hash("AB", "C")
    assert article_content_hash("A", "BC") == article_content_hash("A", "BC")


def test_submission_accepts_http_and_https_url_provenance():
    assert ArticleSubmission(
        url="https://example.org/article?version=1",
        title="Title",
        body="Supplied text",
    ).url == "https://example.org/article?version=1"


def test_submission_rejects_non_http_or_credentialed_url():
    with pytest.raises(ValidationError):
        ArticleSubmission(url="file:///etc/passwd", title="Title", body="Text")
    with pytest.raises(ValidationError):
        ArticleSubmission(
            url="https://user:password@example.org/article",
            title="Title",
            body="Text",
        )
