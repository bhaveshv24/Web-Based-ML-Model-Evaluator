"""Django settings for the ML Model Evaluator API."""

import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-development-key-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [
    host
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,testserver").split(",")
    if host
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
    "evaluations",
    "ingestion",
    "workspaces",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"

if os.environ.get("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ["POSTGRES_DB"],
            "USER": os.environ["POSTGRES_USER"],
            "PASSWORD": os.environ["POSTGRES_PASSWORD"],
            "HOST": os.environ.get("POSTGRES_HOST", "db"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
APPEND_SLASH = False
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))
MEDIA_URL = "/media/"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.PBKDF2PasswordHasher"]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_RATES": {"login": "5/min"},
    "EXCEPTION_HANDLER": "config.exceptions.api_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# --------------------------------------------------------------------------- M3 execution
# Celery + Redis job queue (SAD D-01). Redis is both broker and result backend (SRS 3.2).
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_RESULT_EXPIRES = 3600
# At-least-once delivery (SRS 3.2): ack after the task body runs, never prefetch extra jobs,
# and re-queue when a worker process dies. The task itself is idempotent (claim by CAS).
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_PUBLISH_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5}
CELERY_BROKER_CONNECTION_TIMEOUT = 3
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    "reap-stale-evaluations": {
        "task": "evaluations.reap_stale_evaluations",
        "schedule": 60.0,
    },
}

# FR-019 / BR-03: hard execution limit of the untrusted model run, in seconds.
EVALUATION_TIMEOUT_SECONDS = int(os.environ.get("EVALUATION_TIMEOUT_SECONDS", "120"))
# NFR-006: a RUNNING job older than timeout + grace is reaped (must stay below 5 minutes).
EVALUATION_REAPER_GRACE_SECONDS = int(os.environ.get("EVALUATION_REAPER_GRACE_SECONDS", "60"))
# A job that no worker picked up within this window is failed instead of waiting forever.
EVALUATION_QUEUE_TIMEOUT_SECONDS = int(os.environ.get("EVALUATION_QUEUE_TIMEOUT_SECONDS", "3600"))
# Classification targets with more distinct labels than this are rejected as ambiguous.
EVALUATION_MAX_CLASSES = int(os.environ.get("EVALUATION_MAX_CLASSES", "100"))

# Hardened per-job sandbox (FR-016, SEC-005, SAD 5.1). Values mirror the approved run policy.
SANDBOX_IMAGE = os.environ.get("SANDBOX_IMAGE", "ml-evaluator-sandbox:1.0")
# Docker endpoint. In Compose this is the docker-socket-proxy, never the raw socket.
SANDBOX_DOCKER_URL = os.environ.get("SANDBOX_DOCKER_URL", "")
# Per-job input directories are created here by the worker ...
SANDBOX_WORK_DIR = Path(os.environ.get("SANDBOX_WORK_DIR", BASE_DIR / "sandbox-jobs"))
# ... and this is the same directory as seen by the Docker host (for the read-only bind mount).
SANDBOX_HOST_WORK_DIR = Path(os.environ.get("SANDBOX_HOST_WORK_DIR", str(SANDBOX_WORK_DIR)))
SANDBOX_USER = os.environ.get("SANDBOX_USER", "10001:10001")
SANDBOX_MEMORY_BYTES = int(os.environ.get("SANDBOX_MEMORY_BYTES", str(1024**3)))
SANDBOX_NANO_CPUS = int(os.environ.get("SANDBOX_NANO_CPUS", str(1_000_000_000)))
SANDBOX_PIDS_LIMIT = int(os.environ.get("SANDBOX_PIDS_LIMIT", "128"))
SANDBOX_TMPFS_BYTES = int(os.environ.get("SANDBOX_TMPFS_BYTES", str(64 * 1024**2)))
SANDBOX_MAX_OUTPUT_BYTES = int(os.environ.get("SANDBOX_MAX_OUTPUT_BYTES", str(128 * 1024**2)))
SANDBOX_INSPECT_TIMEOUT_SECONDS = int(os.environ.get("SANDBOX_INSPECT_TIMEOUT_SECONDS", "30"))
SANDBOX_POLL_INTERVAL_SECONDS = float(os.environ.get("SANDBOX_POLL_INTERVAL_SECONDS", "0.5"))
# Compatibility inspection (SAD 5.1 step 6) is dispatched to the worker's sandbox. Off by
# default so a stack without a worker keeps failing closed instead of blocking requests.
SANDBOX_INSPECTION_ENABLED = os.environ.get("SANDBOX_INSPECTION_ENABLED", "0") == "1"
# Dotted path of the sandbox runner class. Deliberately not read from the environment:
# only a settings module (operator-controlled code) can swap the isolation backend.
SANDBOX_RUNNER_CLASS = "evaluations.sandbox.docker_runner.DockerSandboxRunner"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "loggers": {
        "evaluations": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
    },
}
