"""
Celery Beat Schedule Patterns
==============================

Periodic task configuration for a Django content publishing site.
Shows crontab schedules, solar schedules, cleanup tasks, report generation,
and dynamic scheduling with django-celery-beat.

Beat runs periodic tasks on a schedule. It does not execute the tasks itself;
it sends them to the broker for workers to pick up. Only one Beat process
should run at a time to avoid duplicate scheduling.

Start Beat:
    celery -A config beat --loglevel=info

Start Beat with the database scheduler (for dynamic tasks):
    celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler
"""

from celery.schedules import crontab, solar

# ===========================================================================
# Pattern 1: Static Beat schedule with crontab
# ===========================================================================
# Define this in your Celery app config (celery_app.py) or settings.py.
# crontab() follows the same format as Unix cron:
#   crontab(minute, hour, day_of_week, day_of_month, month_of_year)
#
# Defaults: minute="*", hour="*", day_of_week="*", day_of_month="*", month_of_year="*"

CELERY_BEAT_SCHEDULE = {
    # -----------------------------------------------------------------
    # Content maintenance
    # -----------------------------------------------------------------

    # Clean up orphaned draft essays every night at 2:00 AM.
    "cleanup-orphaned-drafts": {
        "task": "apps.content.tasks.cleanup_orphaned_drafts",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {"older_than_days": 90},
        "options": {"queue": "default"},
    },

    # Expire stale rendered markdown every 6 hours.
    # Re-render will happen on next request or next publish cycle.
    "expire-stale-renders": {
        "task": "apps.content.tasks.expire_stale_renders",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        "kwargs": {"stale_threshold_hours": 72},
    },

    # Re-index all published content for search every day at 3:00 AM.
    "rebuild-search-index": {
        "task": "apps.search.tasks.rebuild_full_index",
        "schedule": crontab(hour=3, minute=0),
        "options": {
            "queue": "default",
            "expires": 3600,  # Do not run if delayed more than 1 hour
        },
    },

    # -----------------------------------------------------------------
    # Research source monitoring
    # -----------------------------------------------------------------

    # Check for broken source URLs every Sunday at 4:00 AM.
    "check-broken-source-urls": {
        "task": "apps.research.tasks.check_source_urls",
        "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),
        "options": {"queue": "research"},
    },

    # Refresh source metadata for recently-added sources every 2 hours.
    "refresh-recent-source-metadata": {
        "task": "apps.research.tasks.refresh_recent_metadata",
        "schedule": crontab(minute=30, hour="*/2"),  # Every 2 hours at :30
        "kwargs": {"added_within_days": 7},
        "options": {"queue": "research"},
    },

    # -----------------------------------------------------------------
    # Analytics and reporting
    # -----------------------------------------------------------------

    # Generate daily content analytics summary at 6:00 AM.
    "daily-analytics-summary": {
        "task": "apps.analytics.tasks.generate_daily_summary",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "default"},
    },

    # Generate weekly publishing report on Monday at 7:00 AM.
    "weekly-publishing-report": {
        "task": "apps.analytics.tasks.generate_weekly_report",
        "schedule": crontab(hour=7, minute=0, day_of_week="monday"),
        "options": {"queue": "default"},
    },

    # Generate monthly content health report on the 1st of each month.
    "monthly-content-health": {
        "task": "apps.analytics.tasks.generate_monthly_health_report",
        "schedule": crontab(hour=8, minute=0, day_of_month=1),
        "options": {"queue": "default"},
    },

    # -----------------------------------------------------------------
    # Infrastructure and cache management
    # -----------------------------------------------------------------

    # Warm the cache for popular content every 15 minutes.
    "warm-popular-content-cache": {
        "task": "apps.content.tasks.warm_popular_cache",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
        "options": {"queue": "default", "expires": 600},
    },

    # Clean up expired Celery task results (if using django-db backend).
    "cleanup-task-results": {
        "task": "apps.core.tasks.cleanup_expired_results",
        "schedule": crontab(hour=1, minute=30),
    },

    # Health check: verify worker connectivity every 5 minutes.
    "worker-health-ping": {
        "task": "config.celery.debug_task",
        "schedule": crontab(minute="*/5"),
        "options": {"expires": 240},  # Expire before next ping
    },
}


# ===========================================================================
# Pattern 2: Solar schedule
# ===========================================================================
# Solar schedules trigger tasks based on sunrise/sunset at a given location.
# Useful for content that relates to daylight, weather, or local events.
#
# Supported events:
#   dawn_astronomical, dawn_nautical, dawn_civil, sunrise,
#   solar_noon, sunset, dusk_civil, dusk_nautical, dusk_astronomical

SOLAR_SCHEDULES = {
    # Send a "morning digest" email at sunrise in New York.
    "morning-digest-email": {
        "task": "apps.notifications.tasks.send_morning_digest",
        "schedule": solar("sunrise", lat=40.7128, lon=-74.0060),
        "options": {"queue": "notifications"},
    },

    # Send an "evening reading suggestion" at sunset in New York.
    "evening-reading-suggestion": {
        "task": "apps.notifications.tasks.send_evening_reading",
        "schedule": solar("sunset", lat=40.7128, lon=-74.0060),
        "options": {"queue": "notifications"},
    },
}

# Merge solar schedules into the main beat schedule.
CELERY_BEAT_SCHEDULE.update(SOLAR_SCHEDULES)


# ===========================================================================
# Pattern 3: Periodic cleanup tasks
# ===========================================================================
# These are the actual task implementations referenced in the schedule above.
# In a real project, these would live in their respective apps' tasks.py files.

from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta

logger = get_task_logger(__name__)


@shared_task(ignore_result=True)
def cleanup_orphaned_drafts(older_than_days: int = 90):
    """
    Delete draft essays that have not been modified in a long time.

    These are likely abandoned work. Only deletes drafts (not production
    or published content).
    """
    from apps.content.models import Essay

    cutoff = timezone.now() - timedelta(days=older_than_days)
    orphans = Essay.objects.filter(
        stage="drafting",
        updated_at__lt=cutoff,
    )

    count = orphans.count()
    if count > 0:
        # Archive before deleting, just in case.
        for essay in orphans:
            essay.archive()

        orphans.delete()
        logger.info("Cleaned up %d orphaned draft essays older than %d days.", count, older_than_days)
    else:
        logger.info("No orphaned drafts to clean up.")


@shared_task(ignore_result=True)
def expire_stale_renders(stale_threshold_hours: int = 72):
    """
    Clear rendered markdown that is older than the threshold.

    Forces re-rendering on the next publish cycle so content stays fresh.
    """
    from apps.content.models import Essay

    cutoff = timezone.now() - timedelta(hours=stale_threshold_hours)
    updated = Essay.objects.filter(
        rendered_at__lt=cutoff,
        rendered_markdown__isnull=False,
    ).update(
        rendered_markdown=None,
        rendered_at=None,
    )

    logger.info("Expired %d stale rendered essays.", updated)


@shared_task(ignore_result=True)
def cleanup_expired_results():
    """
    Clean up expired task results from the database.

    Only needed when using django-celery-results as the result backend.
    Results older than result_expires are removed.
    """
    try:
        from django_celery_results.models import TaskResult
    except ImportError:
        logger.warning("django-celery-results not installed. Skipping cleanup.")
        return

    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = TaskResult.objects.filter(date_done__lt=cutoff).delete()
    logger.info("Cleaned up %d expired task results.", deleted)


# ===========================================================================
# Pattern 4: Report generation tasks
# ===========================================================================

@shared_task
def generate_daily_summary() -> dict:
    """
    Generate a daily summary of publishing activity.

    Returns summary data that can be stored or emailed.
    """
    from apps.content.models import Essay, FieldNote
    from apps.research.models import Source

    yesterday = timezone.now() - timedelta(days=1)

    summary = {
        "date": yesterday.date().isoformat(),
        "essays_published": Essay.objects.filter(
            published_at__gte=yesterday,
            stage="published",
        ).count(),
        "essays_in_production": Essay.objects.filter(stage="production").count(),
        "field_notes_published": FieldNote.objects.filter(
            published_at__gte=yesterday,
            stage="published",
        ).count(),
        "sources_added": Source.objects.filter(
            created_at__gte=yesterday,
        ).count(),
        "generated_at": timezone.now().isoformat(),
    }

    logger.info("Daily summary for %s: %s", summary["date"], summary)
    return summary


@shared_task
def generate_weekly_report() -> dict:
    """
    Generate a weekly report of content production and publishing metrics.
    """
    from apps.content.models import Essay, FieldNote, Project

    week_ago = timezone.now() - timedelta(weeks=1)

    report = {
        "period_start": week_ago.date().isoformat(),
        "period_end": timezone.now().date().isoformat(),
        "essays_published": Essay.objects.filter(
            published_at__gte=week_ago,
            stage="published",
        ).count(),
        "essays_started": Essay.objects.filter(
            created_at__gte=week_ago,
        ).count(),
        "field_notes_published": FieldNote.objects.filter(
            published_at__gte=week_ago,
            stage="published",
        ).count(),
        "projects_compiled": Project.objects.filter(
            last_compiled_at__gte=week_ago,
        ).count(),
        "pipeline_stages": {
            "research": Essay.objects.filter(stage="research").count(),
            "drafting": Essay.objects.filter(stage="drafting").count(),
            "production": Essay.objects.filter(stage="production").count(),
            "published": Essay.objects.filter(stage="published").count(),
        },
        "generated_at": timezone.now().isoformat(),
    }

    logger.info("Weekly report: %s", report)
    return report


# ===========================================================================
# Pattern 5: Dynamic periodic tasks with django-celery-beat
# ===========================================================================
# django-celery-beat stores schedules in the database, allowing you to
# create, modify, and delete periodic tasks at runtime without restarting
# Beat. This is useful for user-configured schedules.
#
# Requirements:
#   pip install django-celery-beat
#   INSTALLED_APPS += ["django_celery_beat"]
#   Start Beat with: celery -A config beat --scheduler django_celery_beat.schedulers:DatabaseScheduler

def create_project_compile_schedule(project_id: int, hour: int = 4, minute: int = 0):
    """
    Create a dynamic periodic task that compiles a project every day.

    This allows per-project scheduling without redeploying or restarting Beat.

    Usage:
        create_project_compile_schedule(project_id=7, hour=3, minute=30)
    """
    from django_celery_beat.models import CrontabSchedule, PeriodicTask
    import json

    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=str(minute),
        hour=str(hour),
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="UTC",
    )

    task_name = f"compile-project-{project_id}"

    PeriodicTask.objects.update_or_create(
        name=task_name,
        defaults={
            "task": "apps.content.tasks.compile_project_bundle",
            "crontab": schedule,
            "kwargs": json.dumps({"project_id": project_id}),
            "enabled": True,
            "description": f"Daily compilation for project {project_id}",
            "queue": "content",
        },
    )

    logger.info(
        "Created periodic compile task for project %d at %02d:%02d UTC.",
        project_id,
        hour,
        minute,
    )


def create_source_refresh_schedule(
    source_id: int,
    interval_hours: int = 24,
):
    """
    Create a dynamic interval-based schedule for refreshing a source.

    Uses IntervalSchedule instead of CrontabSchedule for simple intervals.
    """
    from django_celery_beat.models import IntervalSchedule, PeriodicTask
    import json

    schedule, _ = IntervalSchedule.objects.get_or_create(
        every=interval_hours,
        period=IntervalSchedule.HOURS,
    )

    task_name = f"refresh-source-{source_id}"

    PeriodicTask.objects.update_or_create(
        name=task_name,
        defaults={
            "task": "apps.research.tasks.fetch_source_metadata",
            "interval": schedule,
            "args": json.dumps([source_id]),
            "enabled": True,
            "description": f"Refresh metadata for source {source_id} every {interval_hours}h",
            "queue": "research",
        },
    )


def disable_project_schedule(project_id: int):
    """
    Disable the periodic compilation schedule for a project.

    Does not delete the schedule, just disables it so it can be
    re-enabled later.
    """
    from django_celery_beat.models import PeriodicTask

    task_name = f"compile-project-{project_id}"

    updated = PeriodicTask.objects.filter(name=task_name).update(enabled=False)
    if updated:
        logger.info("Disabled periodic compile task for project %d.", project_id)
    else:
        logger.warning("No periodic task found for project %d.", project_id)


def delete_source_schedule(source_id: int):
    """
    Permanently delete the periodic refresh schedule for a source.

    Use this when a source is removed from the system entirely.
    """
    from django_celery_beat.models import PeriodicTask

    task_name = f"refresh-source-{source_id}"

    deleted, _ = PeriodicTask.objects.filter(name=task_name).delete()
    if deleted:
        logger.info("Deleted periodic refresh task for source %d.", source_id)
    else:
        logger.warning("No periodic task found for source %d.", source_id)


def list_active_schedules() -> list:
    """
    List all enabled periodic tasks.

    Useful for admin views and debugging.
    """
    from django_celery_beat.models import PeriodicTask

    tasks = PeriodicTask.objects.filter(enabled=True).values(
        "name",
        "task",
        "enabled",
        "last_run_at",
        "total_run_count",
        "description",
    )

    return list(tasks)
