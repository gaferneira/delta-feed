import hashlib

from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpRequest
from django.middleware.csrf import get_token
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from delta_feed.accounts import setup
from delta_feed.accounts.models import SetupToken

router = Router(tags=["accounts"])

# Brute-force throttle: failures are counted per (client address, username) in the
# Django cache. The default per-process cache is a basic guard for the single-user
# install; configure a shared cache before running several web workers. Behind a
# reverse proxy REMOTE_ADDR is the proxy, so the proxy should be the only client
# of this endpoint or the limit effectively applies per username.
MAX_LOGIN_FAILURES = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60


def _throttle_key(request: HttpRequest, username: str) -> str:
    raw = f"{request.META.get('REMOTE_ADDR', '')}|{username.strip().casefold()}"
    return "login-failures:" + hashlib.sha256(raw.encode()).hexdigest()


class LoginInput(Schema):
    username: str
    password: str


@router.get("/csrf", auth=None)
def csrf_token(request: HttpRequest):
    """Issue a CSRF token for session-authenticated browser mutations and login."""
    return {"csrf_token": get_token(request)}


@router.post("/login", auth=None)
def login_view(request: HttpRequest, payload: LoginInput):
    key = _throttle_key(request, payload.username)
    if cache.get(key, 0) >= MAX_LOGIN_FAILURES:
        raise HttpError(429, "Too many failed login attempts; try again later")
    user = authenticate(
        request,
        username=payload.username,
        password=payload.password,
    )
    if user is None:
        cache.add(key, 0, LOGIN_FAILURE_WINDOW_SECONDS)
        try:
            cache.incr(key)
        except ValueError:  # key expired between add and incr
            cache.set(key, 1, LOGIN_FAILURE_WINDOW_SECONDS)
        raise HttpError(401, "Invalid username or password")
    cache.delete(key)
    login(request, user)
    return {"authenticated": True}


@router.post("/logout")
def logout_view(request: HttpRequest):
    logout(request)
    return {"authenticated": False}


@router.get("/session", auth=None)
def session_view(request: HttpRequest):
    return {"authenticated": request.user.is_authenticated}


@router.get("/setup-status", auth=None)
def setup_status(request: HttpRequest):
    """Report whether first-run setup is open; issues the setup token lazily when it is."""
    needs_setup = setup.needs_setup()
    if needs_setup:
        setup.ensure_setup_token()
    return {"needs_setup": needs_setup}


class SetupInput(Schema):
    token: str
    username: str
    password: str


def _setup_throttle_key(request: HttpRequest) -> str:
    raw = request.META.get("REMOTE_ADDR", "")
    return "setup-failures:" + hashlib.sha256(raw.encode()).hexdigest()


@router.post("/setup", auth=None)
def setup_view(request: HttpRequest, payload: SetupInput):
    key = _setup_throttle_key(request)
    if cache.get(key, 0) >= MAX_LOGIN_FAILURES:
        raise HttpError(429, "Too many failed setup attempts; try again later")

    user_model = get_user_model()
    # Locking the single token row serializes concurrent setup attempts: the loser
    # re-checks for a user after the winner commits and gets 409.
    with transaction.atomic():
        stored = SetupToken.objects.select_for_update().filter(slot=1).first()
        if user_model.objects.exists():
            raise HttpError(409, "Setup is already complete")
        if stored is None or stored.expires_at <= timezone.now() or not setup.token_matches(
            stored, payload.token.strip()
        ):
            cache.add(key, 0, LOGIN_FAILURE_WINDOW_SECONDS)
            try:
                cache.incr(key)
            except ValueError:  # key expired between add and incr
                cache.set(key, 1, LOGIN_FAILURE_WINDOW_SECONDS)
            raise HttpError(403, "Invalid or expired setup token")

        user = user_model(username=payload.username)
        try:
            user.clean_fields(exclude=["password"])
            validate_password(payload.password, user)
        except ValidationError as error:
            raise HttpError(400, " ".join(error.messages)) from error
        user.set_password(payload.password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        stored.delete()

    cache.delete(key)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return {"authenticated": True}
