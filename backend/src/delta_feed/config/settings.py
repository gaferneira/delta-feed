"""Django settings for Delta Feed."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parents[3]


def _env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes"}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return max(0, int(value))
    except ValueError as exc:
        raise ImproperlyConfigured(f"{name} must be a non-negative integer") from exc


_INSECURE_DEV_KEY = "insecure-development-key-do-not-use-in-production"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", _INSECURE_DEV_KEY)
DEBUG = _env_flag("DJANGO_DEBUG", False)

# Fail fast: a deployment (DEBUG off) must never run with the published dev key
# or a weak one. Local development opts in with DJANGO_DEBUG=true; automated
# tests opt in explicitly with DJANGO_ALLOW_INSECURE_DEV_KEY=true.
if not DEBUG and not _env_flag("DJANGO_ALLOW_INSECURE_DEV_KEY", False) and (
    SECRET_KEY == _INSECURE_DEV_KEY or len(SECRET_KEY) < 50
):
    raise ImproperlyConfigured(
        "Set DJANGO_SECRET_KEY to a unique random value of at least 50 characters, "
        "or set DJANGO_DEBUG=true for local development."
    )

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

# Session-cookie auth. The CSRF cookie must stay readable by the reader's browser
# code (it echoes it in X-CSRFToken), so CSRF_COOKIE_HTTPONLY is deliberately False.
_SECURE_COOKIES = _env_flag("DJANGO_SECURE_COOKIES", not DEBUG)
SESSION_COOKIE_SECURE = _SECURE_COOKIES
CSRF_COOKIE_SECURE = _SECURE_COOKIES
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
# Origins of the public reader (scheme://host[:port]) that may submit unsafe requests.
# Local development defaults to the Astro dev server; real deployments must set it explicitly.
_DEV_TRUSTED_ORIGINS = "http://localhost:4321,http://127.0.0.1:4321" if DEBUG else ""
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", _DEV_TRUSTED_ORIGINS).split(",")
    if origin.strip()
]
if _env_flag("DJANGO_BEHIND_TLS_PROXY", False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if _SECURE_COOKIES:
    SECURE_SSL_REDIRECT = _env_flag("DJANGO_SSL_REDIRECT", False)
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "0"))
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "delta_feed.accounts.apps.AccountsConfig",
    "delta_feed.content.apps.ContentConfig",
    "delta_feed.reader.apps.ReaderConfig",
    "delta_feed.guides.apps.GuidesConfig",
    "delta_feed.jobs.apps.JobsConfig",
    "delta_feed.knowledge.apps.KnowledgeConfig",
    "delta_feed.analysis.apps.AnalysisConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "delta_feed.config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "delta_feed.config.wsgi.application"
ASGI_APPLICATION = "delta_feed.config.asgi.application"

# SQLite keeps the initial local/test slice runnable without a PostgreSQL service.
# Set DB_ENGINE=postgresql for deployments; pgvector extensions are not required here.
if os.environ.get("DB_ENGINE", "sqlite").lower() == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME", "delta_feed"),
            "USER": os.environ.get("DB_USER", "delta_feed"),
            "PASSWORD": os.environ.get("DB_PASSWORD", ""),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.environ.get("SQLITE_PATH", str(BASE_DIR / "db.sqlite3")),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Versioned starter packs (topic + suggested feeds) offered during onboarding.
STARTER_PACKS_DIR = Path(os.environ.get("STARTER_PACKS_DIR", str(BASE_DIR.parent / "starter-packs")))

# Attention budgets (ADR 0006, Phase A). Ingestion is bounded at first import and
# polled on a schedule; Today shows a limited, source-diverse selection.
BACKFILL_DAYS = _env_int("BACKFILL_DAYS", 30)
BACKFILL_MAX_ITEMS = _env_int("BACKFILL_MAX_ITEMS", 20)
RSS_POLL_INTERVAL_MINUTES = _env_int("RSS_POLL_INTERVAL_MINUTES", 30)
TODAY_BUDGET = _env_int("TODAY_BUDGET", 12)
TODAY_PER_SOURCE_CAP = _env_int("TODAY_PER_SOURCE_CAP", 3)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
