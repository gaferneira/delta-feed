import json
import logging
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone

from delta_feed.accounts import setup
from delta_feed.accounts.models import SetupToken

pytestmark = pytest.mark.django_db

GOOD_PASSWORD = "correct-horse-battery-9"


@pytest.fixture(autouse=True)
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def issue_token(caplog) -> str:
    """Trigger lazy issuance through the API and read the plaintext back from the log."""
    with caplog.at_level(logging.WARNING, logger="delta_feed.accounts.setup"):
        assert Client().get("/api/accounts/setup-status").json() == {"needs_setup": True}
    message = caplog.records[-1].getMessage()
    return message.split("setup token: ")[1].split(" ")[0]


def post_setup(client, token, username="owner", password=GOOD_PASSWORD):
    return client.post(
        "/api/accounts/setup",
        data=json.dumps({"token": token, "username": username, "password": password}),
        content_type="application/json",
    )


def test_needs_setup_reflects_user_existence(caplog):
    assert Client().get("/api/accounts/setup-status").json() == {"needs_setup": True}
    get_user_model().objects.create_user(username="someone", password=GOOD_PASSWORD)
    assert Client().get("/api/accounts/setup-status").json() == {"needs_setup": False}


def test_no_token_is_issued_once_a_user_exists(caplog):
    get_user_model().objects.create_user(username="someone", password=GOOD_PASSWORD)
    Client().get("/api/accounts/setup-status")
    assert SetupToken.objects.count() == 0


def test_token_is_issued_once_logged_once_and_stored_only_as_hash(caplog):
    token = issue_token(caplog)
    for _ in range(3):
        Client().get("/api/accounts/setup-status")
    warnings = [r for r in caplog.records if "setup token" in r.getMessage()]
    assert len(warnings) == 1
    assert "/setup" in warnings[0].getMessage() and "expires" in warnings[0].getMessage()
    row = SetupToken.objects.get()
    assert row.token_hash == setup.hash_token(token) != token
    assert timedelta(hours=23) < row.expires_at - timezone.now() <= timedelta(hours=24)


def test_expired_token_is_replaced_on_next_status_check(caplog):
    first = issue_token(caplog)
    SetupToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    second = issue_token(caplog)
    assert first != second
    assert SetupToken.objects.count() == 1
    assert setup.token_matches(SetupToken.objects.get(), second)


def test_lost_issuance_race_leaves_exactly_one_valid_token(caplog):
    token = issue_token(caplog)
    # Simulate a concurrent issuer that did not see the committed row: its insert must
    # hit the unique slot constraint and issue (and log) nothing.
    with patch("delta_feed.accounts.setup.SetupToken.objects.select_for_update") as locked:
        locked.return_value.filter.return_value.first.return_value = None
        assert setup.ensure_setup_token() is False
    assert SetupToken.objects.count() == 1
    assert setup.token_matches(SetupToken.objects.get(), token)
    assert len([r for r in caplog.records if "setup token" in r.getMessage()]) == 1


def test_setup_creates_superuser_deletes_token_and_logs_in(caplog):
    token = issue_token(caplog)
    client = Client(enforce_csrf_checks=False)
    response = post_setup(client, token)
    assert response.status_code == 200 and response.json() == {"authenticated": True}
    user = get_user_model().objects.get(username="owner")
    assert user.is_superuser and user.is_staff and user.check_password(GOOD_PASSWORD)
    assert SetupToken.objects.count() == 0
    assert client.get("/api/accounts/session").json() == {"authenticated": True}
    assert Client().get("/api/accounts/setup-status").json() == {"needs_setup": False}
    assert SetupToken.objects.count() == 0


def test_setup_rejects_wrong_token(caplog):
    issue_token(caplog)
    response = post_setup(Client(), "not-the-token")
    assert response.status_code == 403
    assert not get_user_model().objects.exists()
    assert SetupToken.objects.count() == 1


def test_setup_rejects_expired_token(caplog):
    token = issue_token(caplog)
    SetupToken.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
    assert post_setup(Client(), token).status_code == 403
    assert not get_user_model().objects.exists()


def test_setup_rejects_when_no_token_was_issued():
    assert post_setup(Client(), "anything").status_code == 403


def test_failed_token_attempts_are_throttled(caplog):
    token = issue_token(caplog)
    assert [post_setup(Client(), "wrong").status_code for _ in range(5)] == [403] * 5
    assert post_setup(Client(), "wrong").status_code == 429
    assert post_setup(Client(), token).status_code == 429
    assert not get_user_model().objects.exists()
    cache.clear()
    assert post_setup(Client(), token).status_code == 200


def test_setup_returns_409_when_a_user_exists(caplog):
    token = issue_token(caplog)
    get_user_model().objects.create_user(username="early", password=GOOD_PASSWORD)
    response = post_setup(Client(), token)
    assert response.status_code == 409
    assert get_user_model().objects.count() == 1


def test_second_setup_with_same_token_is_refused(caplog):
    token = issue_token(caplog)
    assert post_setup(Client(), token).status_code == 200
    assert post_setup(Client(), token, username="intruder").status_code == 409
    assert get_user_model().objects.count() == 1


@pytest.mark.parametrize("password", ["short1", "password", "12345678901234"])
def test_setup_rejects_weak_passwords_with_validator_messages(caplog, password):
    token = issue_token(caplog)
    response = post_setup(Client(), token, password=password)
    assert response.status_code == 400
    assert response.json()["detail"]
    assert not get_user_model().objects.exists()
    assert SetupToken.objects.count() == 1  # a weak password does not burn the token


def test_setup_rejects_password_similar_to_username(caplog):
    token = issue_token(caplog)
    response = post_setup(Client(), token, username="gabrielowner", password="gabrielowner1")
    assert response.status_code == 400


@pytest.mark.parametrize("username", ["", "   ", "bad name!", "x" * 151])
def test_setup_rejects_invalid_usernames(caplog, username):
    token = issue_token(caplog)
    assert post_setup(Client(), token, username=username).status_code == 400
    assert not get_user_model().objects.exists()


def test_setup_enforces_csrf(caplog):
    token = issue_token(caplog)
    client = Client(enforce_csrf_checks=True)
    assert post_setup(client, token).status_code == 403
    assert not get_user_model().objects.exists()
    assert SetupToken.objects.count() == 1

    csrf = client.get("/api/accounts/csrf").json()["csrf_token"]
    response = client.post(
        "/api/accounts/setup",
        data=json.dumps({"token": token, "username": "owner", "password": GOOD_PASSWORD}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    assert get_user_model().objects.filter(username="owner").exists()


def test_setup_token_command_rotates_and_invalidates_the_old_token(caplog):
    old = issue_token(caplog)
    out = StringIO()
    call_command("setup_token", stdout=out, stderr=StringIO())
    new = out.getvalue().strip()
    assert new and new != old
    assert SetupToken.objects.count() == 1
    assert setup.token_matches(SetupToken.objects.get(), new)
    assert post_setup(Client(), old).status_code == 403
    assert post_setup(Client(), new).status_code == 200


def test_setup_token_command_issues_when_none_exists():
    out = StringIO()
    call_command("setup_token", stdout=out, stderr=StringIO())
    assert setup.token_matches(SetupToken.objects.get(), out.getvalue().strip())


def test_setup_token_command_refuses_when_a_user_exists():
    get_user_model().objects.create_user(username="someone", password=GOOD_PASSWORD)
    with pytest.raises(CommandError, match="already exists"):
        call_command("setup_token", stdout=StringIO(), stderr=StringIO())
    assert SetupToken.objects.count() == 0
