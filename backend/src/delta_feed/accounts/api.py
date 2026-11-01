import hashlib

from django.contrib.auth import authenticate, login, logout
from django.core.cache import cache
from django.http import HttpRequest
from django.middleware.csrf import get_token
from ninja import Router, Schema
from ninja.errors import HttpError

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
