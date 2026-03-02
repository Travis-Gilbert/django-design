"""
Celery Application Setup
=========================

Standard Celery configuration for a Django content publishing site.
Shows app creation, autodiscovery, serialization, routing, and limits.

Usage:
    # In your Django project's config/__init__.py:
    from .celery import app as celery_app
    __all__ = ("celery_app",)
"""

import os

from celery import Celery

# ---------------------------------------------------------------------------
# 1. Set Django settings before creating the app
# ---------------------------------------------------------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("publishing")

# ---------------------------------------------------------------------------
# 2. Load config from Django settings, namespaced under CELERY_
# ---------------------------------------------------------------------------
# Any setting prefixed with CELERY_ in settings.py will be picked up.
# Example: CELERY_BROKER_URL in settings.py becomes broker_url here.
app.config_from_object("django.conf:settings", namespace="CELERY")

# ---------------------------------------------------------------------------
# 3. Auto-discover tasks in all installed Django apps
# ---------------------------------------------------------------------------
# Looks for a tasks.py module in each INSTALLED_APPS entry.
app.autodiscover_tasks()

# ---------------------------------------------------------------------------
# 4. Serialization -- always use JSON for safety
# ---------------------------------------------------------------------------
# JSON is safe, readable, and sufficient for most payloads.
# Never allow untrusted deserialization formats in production.
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]

# ---------------------------------------------------------------------------
# 5. Result backend
# ---------------------------------------------------------------------------
# django-celery-results stores results in your Django database.
# For high-volume results, consider Redis if you only need short-lived
# results, or RPC (amqp) if you only need the result once.
app.conf.result_backend = "django-db"  # django-celery-results
# Alternative: app.conf.result_backend = "redis://localhost:6379/1"

# Results expire after 24 hours to prevent unbounded storage growth.
app.conf.result_expires = 60 * 60 * 24  # 24 hours in seconds

# ---------------------------------------------------------------------------
# 6. Task routes -- send tasks to the right queues
# ---------------------------------------------------------------------------
# Routing separates concerns: fast tasks should not get stuck behind
# slow ones. Define queues by workload characteristics, not by app.
app.conf.task_routes = {
    # Content processing is CPU-bound and can be slow.
    "apps.content.tasks.render_essay_to_markdown": {"queue": "content"},
    "apps.content.tasks.process_essay_images": {"queue": "content"},
    "apps.content.tasks.compile_project_bundle": {"queue": "content"},

    # Video processing is very slow and resource-intensive.
    "apps.video.tasks.*": {"queue": "video"},

    # Research tasks hit external APIs and should be rate-limited separately.
    "apps.research.tasks.*": {"queue": "research"},

    # Notifications are fast and high-priority.
    "apps.notifications.tasks.*": {"queue": "notifications"},

    # Everything else goes to the default queue.
}

# Define default queue for tasks without explicit routing.
app.conf.task_default_queue = "default"

# ---------------------------------------------------------------------------
# 7. Time limits -- prevent runaway tasks
# ---------------------------------------------------------------------------
# soft_time_limit raises SoftTimeLimitExceeded so the task can clean up.
# task_time_limit kills the worker process (hard limit).
app.conf.task_soft_time_limit = 300  # 5 minutes
app.conf.task_time_limit = 360  # 6 minutes (hard kill)

# Override per-task in the task decorator or routes:
app.conf.task_annotations = {
    "apps.video.tasks.transcode_video": {
        "time_limit": 3600,       # 1 hour hard limit
        "soft_time_limit": 3300,  # 55 minutes soft limit
    },
    "apps.content.tasks.compile_project_bundle": {
        "time_limit": 600,
        "soft_time_limit": 540,
    },
}

# ---------------------------------------------------------------------------
# 8. Rate limits -- protect external services
# ---------------------------------------------------------------------------
app.conf.task_annotations.update({
    # Do not hammer the image CDN: max 10 requests per minute.
    "apps.content.tasks.upload_image_to_cdn": {
        "rate_limit": "10/m",
    },
    # External research API: max 30 requests per minute.
    "apps.research.tasks.fetch_source_metadata": {
        "rate_limit": "30/m",
    },
})

# ---------------------------------------------------------------------------
# 9. Worker settings
# ---------------------------------------------------------------------------
# Prefetch multiplier controls how many messages the worker grabs at once.
# Lower values give fairer distribution across workers.
# Set to 1 for long-running tasks so one worker does not hoard them.
app.conf.worker_prefetch_multiplier = 4

# For the video queue, prefetch just 1 (configured per worker at startup):
# celery -A config worker -Q video --concurrency=2 -Ofair

# Acknowledge tasks after they complete, not when received.
# Prevents task loss if a worker crashes mid-execution.
app.conf.task_acks_late = True
app.conf.worker_cancel_long_running_tasks_on_connection_loss = True

# ---------------------------------------------------------------------------
# 10. Timezone -- match Django
# ---------------------------------------------------------------------------
app.conf.timezone = "UTC"
app.conf.enable_utc = True


# ---------------------------------------------------------------------------
# Debug task -- useful during development
# ---------------------------------------------------------------------------
@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Print request info. Useful for verifying worker connectivity."""
    print(f"Request: {self.request!r}")
