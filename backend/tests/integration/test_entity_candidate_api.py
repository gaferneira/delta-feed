import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from delta_feed.knowledge.models import Entity, EntityEmbedding

pytestmark = pytest.mark.django_db


def post_json(client, path, payload):
    return client.post(path, data=json.dumps(payload), content_type="application/json")


def test_candidates_endpoint_is_authenticated_and_returns_suggestions_without_merging():
    user = get_user_model().objects.create_user(username="candidate-reviewer", password="password")
    client = Client()
    client.force_login(user)
    first = Entity.objects.create(name="Widget", type="software")
    second = Entity.objects.create(name="Gadget", type="software")
    EntityEmbedding.objects.create(entity=first, model_version="test-v1", vector=[1.0, 0.0])
    EntityEmbedding.objects.create(entity=second, model_version="test-v1", vector=[0.8, 0.6])
    original_count = Entity.objects.count()

    response = post_json(
        client,
        "/api/knowledge/entities/candidates",
        {"identifiers": {}, "embedding": [1.0, 0.0], "model_version": "test-v1", "limit": 10},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["entity"]["id"] for item in body["candidates"]] == [first.pk, second.pk]
    assert [item["similarity"] for item in body["candidates"]] == pytest.approx([1.0, 0.8])
    assert body["auto_merged"] is False
    assert Entity.objects.count() == original_count
    assert Entity.objects.get(pk=first.pk).name == "Widget"


def test_candidates_endpoint_requires_authentication():
    response = post_json(
        Client(),
        "/api/knowledge/entities/candidates",
        {"identifiers": {}, "embedding": [1.0, 0.0], "model_version": "test-v1"},
    )

    assert response.status_code == 401


def test_match_endpoint_returns_ranked_candidates_when_exact_identifiers_miss():
    user = get_user_model().objects.create_user(username="fallback-reviewer", password="password")
    client = Client()
    client.force_login(user)
    candidate = Entity.objects.create(name="Likely Widget", type="software")
    EntityEmbedding.objects.create(entity=candidate, model_version="test-v1", vector=[1.0, 0.0])

    response = post_json(
        client,
        "/api/knowledge/entities/match",
        {
            "identifiers": {"repository": "owner/unknown"},
            "embedding": [1.0, 0.0],
            "model_version": "test-v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entity"] is None
    assert [item["entity"]["id"] for item in body["candidates"]] == [candidate.pk]
    assert Entity.objects.count() == 1


def test_existing_exact_match_prevents_embedding_candidate_fallback():
    user = get_user_model().objects.create_user(username="exact-reviewer", password="password")
    client = Client()
    client.force_login(user)
    exact = Entity.objects.create(
        name="Exact", type="software", identifiers={"repository": "owner/exact"}
    )
    other = Entity.objects.create(name="Other", type="software")
    EntityEmbedding.objects.create(entity=other, model_version="test-v1", vector=[1.0, 0.0])

    response = post_json(
        client,
        "/api/knowledge/entities/match",
        {
            "identifiers": {"repository": "owner/exact"},
            "embedding": [1.0, 0.0],
            "model_version": "test-v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entity"]["id"] == exact.pk
    assert body["candidates"] == []
