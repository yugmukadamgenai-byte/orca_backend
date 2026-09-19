"""
Django settings for orca_backend project.
Configured to run locally with SQLite for testing, and on Render.com
(free tier) with Postgres in production - controlled entirely by
environment variables, so no code changes are needed between the two.
"""

import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY: set a real secret in production via the SECRET_KEY env var.
# This fallback is only for local development - never use it live.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")

# Render sets RENDER=true automatically; use that to detect production.
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"

# Fail loudly rather than silently: if DEBUG is off (production) but
# nobody ever set a real SECRET_KEY, that's a serious misconfiguration -
# better to crash on startup with a clear message than to quietly run a
# public site with a well-known, guessable secret key.
if not DEBUG and SECRET_KEY == "dev-only-insecure-key-change-me":
    raise RuntimeError(
        "SECRET_KEY is not set. Set a real random value via the SECRET_KEY "
        "environment variable in Render's dashboard before running in production."
    )

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Shared secret your local PC uses to authenticate push requests
# (orchestrator.py / scheduler.py). Set this to a real random string
# via the PUSH_API_KEY env var in production, and match it in your
# local push_to_backend.py config.
PUSH_API_KEY = os.environ.get("PUSH_API_KEY", "dev-only-local-key")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "orca_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "orca_backend.wsgi.application"

# DATABASE_URL env var (set automatically by Render when you attach a
# free Postgres instance) takes over in production. Falls back to a
# local SQLite file for development.
#
# conn_max_age=0 (rather than a persistent value like 600) is important
# specifically because Neon's free tier auto-suspends the database after
# inactivity. A "persistent" connection Django tries to reuse can already
# be dead on Neon's end by the time the next request comes in, causing
# "SSL connection has been closed unexpectedly" errors. Opening a fresh
# connection per request avoids that, at the small cost of a bit more
# per-request connection overhead - a reasonable trade for a serverless
# free-tier database.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    # Without pagination, /readings/ and /agent-runs/ would return every
    # row ever recorded in one response. With the scheduler polling every
    # 3 minutes across 10 locations, that grows by ~4,800 rows/day - this
    # keeps individual responses small and fast regardless of how much
    # history has piled up.
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    # Rate limiting: every GET endpoint is intentionally open with no
    # login (see API_INTEGRATION_GUIDE.md), which means anyone - not just
    # your app - can hit it. These caps stop one misbehaving client (a
    # buggy app retry loop, a scraper, deliberate abuse) from exhausting
    # Render's and Neon's free-tier limits for everyone. Adjust upward if
    # real usage legitimately needs more.
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/minute"},
    # Ensures a client error (bad request) never becomes an unhandled
    # 500 - DRF's default exception handler already does this for
    # standard cases; being explicit here documents the intent.
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
}

# --- Production security hardening (only actually applies when DEBUG=False,
# i.e. on Render - these would just get in the way of local development) ---
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 7  # 1 week - raise once confident nothing breaks
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # Render terminates SSL at its own proxy and forwards plain HTTP
    # internally - without this, Django can't tell the original request
    # was HTTPS and SECURE_SSL_REDIRECT would cause a redirect loop.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Logging: makes real errors visible in Render's log tab. Without
# this, an unhandled exception in production (DEBUG=False) fails silently
# from your perspective - the user just gets a generic error page and you
# have no way to know it happened. ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            # Specifically surfaces 500 errors with full tracebacks in
            # Render's logs, even though DEBUG=False hides them from users.
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
