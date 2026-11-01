import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delta_feed.content.models import Article, ArticleRevision
from delta_feed.reader.models import ReadState, SaveState

pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        username="reader", password="correct-horse-battery"
    )


@pytest.fixture
def client(user):
    client = Client()
    client.force_login(user)
    return client


def post_json(client, path, payload):
    return client.post(
        path,
        data=json.dumps(payload),
        content_type="application/json",
    )


def test_authenticated_submission_creates_article_and_first_revision(client):
    response = post_json(
        client,
        "/api/content/articles",
        {
            "url": "https://example.org/releases/1",
            "title": "Release one",
            "body": "Original article text",
        },
    )

    assert response.status_code == 201
    result = response.json()
    assert result["article_id"] == Article.objects.get().id
    assert result["revision_number"] == 1
    assert ArticleRevision.objects.count() == 1


def test_resubmission_appends_revision_to_existing_article(client):
    payload = {
        "url": "https://example.org/releases/1",
        "title": "Release one",
        "body": "Original article text",
    }
    first = post_json(client, "/api/content/articles", payload)
    updated = post_json(
        client,
        "/api/content/articles",
        {**payload, "title": "Release one, corrected", "body": "Corrected text"},
    )

    assert first.status_code == 201
    assert updated.status_code == 200
    assert updated.json()["article_id"] == first.json()["article_id"]
    assert updated.json()["revision_number"] == 2
    assert Article.objects.count() == 1
    assert list(ArticleRevision.objects.order_by("version").values_list("version", flat=True)) == [1, 2]


def test_read_and_save_state_appear_in_personalized_feed(client):
    submitted = post_json(
        client,
        "/api/content/articles",
        {
            "url": "https://example.org/releases/reader-state",
            "title": "Reader state article",
            "body": "Article body",
        },
    ).json()
    article_id = submitted["article_id"]

    read_response = post_json(
        client, f"/api/reader/articles/{article_id}/read", {"read": True}
    )
    save_response = post_json(
        client, f"/api/reader/articles/{article_id}/save", {"saved": True}
    )
    feed_response = client.get("/api/reader/feed")

    assert read_response.status_code == save_response.status_code == 200
    assert ReadState.objects.get(article_id=article_id).is_read is True
    assert SaveState.objects.get(article_id=article_id).is_saved is True
    assert feed_response.status_code == 200
    item = feed_response.json()["items"][0]
    assert item["article_id"] == article_id
    assert item["is_read"] is True
    assert item["is_saved"] is True
    assert item["title"] == "Reader state article"

    other_user = get_user_model().objects.create_user(username="other-reader")
    other_client = Client()
    other_client.force_login(other_user)
    other_item = other_client.get("/api/reader/feed").json()["items"][0]
    assert other_item["is_read"] is False
    assert other_item["is_saved"] is False


def test_all_content_and_reader_endpoints_require_authentication():
    anonymous = Client()
    paths = [
        ("get", "/api/reader/feed"),
        ("post", "/api/content/articles", {"url": "https://example.org/a", "title": "A", "body": "B"}),
        ("post", "/api/reader/articles/1/read", {"read": True}),
        ("post", "/api/reader/articles/1/save", {"saved": True}),
    ]

    for method, path, *body in paths:
        response = getattr(anonymous, method)(
            path,
            **(
                {"data": json.dumps(body[0]), "content_type": "application/json"}
                if body
                else {}
            ),
        )
        assert response.status_code == 401, path


def test_login_establishes_a_django_session():
    user = get_user_model().objects.create_user(
        username="session-reader", password="correct-horse-battery"
    )
    client = Client()

    response = post_json(
        client,
        "/api/accounts/login",
        {"username": user.username, "password": "correct-horse-battery"},
    )

    assert response.status_code == 200
    assert response.json() == {"authenticated": True}
    assert client.get("/api/reader/feed").status_code == 200
    logout_response = post_json(client, "/api/accounts/logout", {})
    assert logout_response.status_code == 200
    assert logout_response.json() == {"authenticated": False}
    assert client.get("/api/reader/feed").status_code == 401


def test_unchanged_resubmission_does_not_create_duplicate_revision(client):
    payload = {
        "url": "https://example.org/releases/unchanged",
        "title": "Stable",
        "body": "Same article text",
    }
    post_json(client, "/api/content/articles", payload)
    response = post_json(client, "/api/content/articles", payload)

    assert response.status_code == 200
    assert response.json()["revision_number"] == 1
    assert Article.objects.count() == 1
    assert ArticleRevision.objects.count() == 1


def test_login_and_article_mutations_enforce_django_csrf(user):
    client = Client(enforce_csrf_checks=True)
    token_response = client.get("/api/accounts/csrf")
    csrf_token = token_response.json()["csrf_token"]

    login_response = post_json(
        client,
        "/api/accounts/login",
        {"username": user.username, "password": "correct-horse-battery"},
    )
    assert login_response.status_code == 403

    login_response = client.post(
        "/api/accounts/login",
        data=json.dumps(
            {"username": user.username, "password": "correct-horse-battery"}
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert login_response.status_code == 200

    missing_token = post_json(
        client,
        "/api/content/articles",
        {"url": "https://example.org/csrf", "title": "CSRF", "body": "Text"},
    )
    assert missing_token.status_code == 403

    mutation_token = client.cookies["csrftoken"].value
    accepted = client.post(
        "/api/content/articles",
        data=json.dumps(
            {"url": "https://example.org/csrf", "title": "CSRF", "body": "Text"}
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=mutation_token,
    )
    assert accepted.status_code == 201
