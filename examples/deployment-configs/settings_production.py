"""
Production Django settings.

This module extends your base settings with production-specific overrides.
All secrets and host-specific values come from environment variables so this
file is safe to commit to version control.

Usage in your settings package:
    myproject/settings/__init__.py  (or base.py)
    myproject/settings/production.py  <-- this file

Set DJANGO_SETTINGS_MODULE=myproject.settings.production in your environment.
"""

import os
import logging

import dj_database_url
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

# Import everything from the base settings module.
from .base import *  # noqa: F401, F403


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Comma-separated list in the environment, e.g. "example.com,www.example.com"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")

# For running behind a reverse proxy (Nginx, ALB, CloudFront).
# The proxy sets X-Forwarded-Proto so Django knows the original scheme.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

# dj-database-url parses DATABASE_URL into the dict Django expects.
# Examples:
#   postgres://user:pass@host:5432/dbname
#   postgres://user:pass@host:5432/dbname?sslmode=require
DATABASES = {
    "default": dj_database_url.config(
        default=os.environ.get("DATABASE_URL"),
        conn_max_age=600,
        conn_health_checks=True,
        ssl_require=os.environ.get("DATABASE_SSL", "true").lower() == "true",
    )
}


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "parser_class": "redis.connection.HiredisParser",
        },
        "KEY_PREFIX": os.environ.get("CACHE_KEY_PREFIX", "prod"),
        "TIMEOUT": int(os.environ.get("CACHE_TIMEOUT", "300")),
    }
}

# Use cache-backed sessions for better performance. The default database
# backend writes a row per session; Redis is faster and auto-expires.
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"


# ---------------------------------------------------------------------------
# Static files (WhiteNoise)
# ---------------------------------------------------------------------------

# WhiteNoise serves static files directly from the WSGI application,
# removing the need for Nginx to handle /static/. It adds far-future
# cache headers and Brotli/gzip compression automatically.
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Insert WhiteNoise after SecurityMiddleware. It must come before all
# other middleware so it can intercept static file requests early.
# This assumes MIDDLEWARE is defined in base settings as a list.
try:
    _security_index = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")  # noqa: F405
    MIDDLEWARE.insert(_security_index + 1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
except ValueError:
    MIDDLEWARE.insert(0, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # noqa: F405


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

# HTTPS enforcement
SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() == "true"

# HTTP Strict Transport Security.
# Start with a short max-age (3600) and increase to 31536000 (1 year) after
# verifying everything works over HTTPS.
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Cookies
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# Prevent browsers from guessing content types.
SECURE_CONTENT_TYPE_NOSNIFF = True

# Trusted origins for CSRF. Required when running behind a proxy on a
# different domain or port.
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS", ""
).split(",") if os.environ.get("CSRF_TRUSTED_ORIGINS") else []


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

# Choose backend via environment variable.
# "smtp"  -> Django's built-in SMTP backend
# "ses"   -> django-ses for Amazon SES (pip install django-ses)
_email_backend = os.environ.get("EMAIL_BACKEND", "smtp")

if _email_backend == "ses":
    EMAIL_BACKEND = "django_ses.SESBackend"
    AWS_SES_REGION_NAME = os.environ.get("AWS_SES_REGION", "us-east-1")
    AWS_SES_REGION_ENDPOINT = f"email.{AWS_SES_REGION_NAME}.amazonaws.com"
    # AWS credentials come from IAM role, env vars, or ~/.aws/credentials.
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@example.com")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)


# ---------------------------------------------------------------------------
# Sentry (error tracking)
# ---------------------------------------------------------------------------

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style="url",
                middleware_spans=True,
            ),
            CeleryIntegration(monitor_beat_tasks=True),
            LoggingIntegration(
                level=logging.INFO,        # Breadcrumbs from INFO and above
                event_level=logging.ERROR,  # Send events for ERROR and above
            ),
        ],
        # Capture 10% of transactions for performance monitoring.
        # Adjust based on traffic volume and Sentry plan.
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        # Associate errors with releases for deploy tracking.
        release=os.environ.get("APP_VERSION", "unknown"),
        environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        # Scrub sensitive data from events.
        send_default_pii=False,
    )


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

# Structured logging suitable for log aggregators (CloudWatch, Datadog, ELK).
# In production, log to stdout/stderr and let the container runtime or
# systemd handle log routing.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "format": (
                "%(asctime)s %(levelname)s %(name)s %(module)s "
                "%(process)d %(thread)d %(message)s"
            ),
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": (
                "%(asctime)s %(levelname)s %(name)s %(module)s "
                "%(funcName)s %(lineno)d %(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": os.environ.get("LOG_FORMAT", "structured"),
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("DJANGO_LOG_LEVEL", "WARNING"),
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "WARNING"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Application logger. Use logging.getLogger("myproject") in your code.
        "myproject": {
            "handlers": ["console"],
            "level": os.environ.get("APP_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        # Celery task logger.
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/0")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1


# ---------------------------------------------------------------------------
# Media files (user uploads)
# ---------------------------------------------------------------------------

# For production, store media in S3 or similar object storage.
# pip install django-storages[s3]
#
# Uncomment and configure:
# STORAGES["default"] = {
#     "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
# }
# AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
# AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
# AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN")
# AWS_DEFAULT_ACL = None
# AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
