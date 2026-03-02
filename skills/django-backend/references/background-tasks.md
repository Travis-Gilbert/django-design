# Django Background Tasks Reference

## When to Use Background Tasks

A web request should complete in under a few seconds. When work takes longer or does not need to block the user, move it to a background task. Common candidates:

- Sending emails and notifications
- Generating reports and PDFs
- Processing file uploads (resizing images, parsing CSVs)
- Syncing data with external APIs
- Running periodic maintenance (cleanup, aggregation, cache warming)
- Any operation where failure should not crash the user's request

## Task Queue Options

### Celery

The most widely used task queue for Django. Full-featured, battle-tested, complex to operate.

```python
# pip install celery[redis] django-celery-beat

# project_name/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_name.settings')

app = Celery('project_name')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


# project_name/__init__.py
from .celery import app as celery_app

__all__ = ['celery_app']


# settings/base.py
CELERY_BROKER_URL = env('REDIS_URL', default='redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minute hard limit
CELERY_TASK_SOFT_TIME_LIMIT = 240  # 4 minute soft limit (raises SoftTimeLimitExceeded)
```

### django-rq

Simpler than Celery, backed by Redis Queue. Good for projects that do not need Celery's full feature set.

```python
# pip install django-rq

# settings/base.py
RQ_QUEUES = {
    'default': {
        'URL': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
        'DEFAULT_TIMEOUT': 300,
    },
    'low': {
        'URL': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
        'DEFAULT_TIMEOUT': 600,
    },
}

INSTALLED_APPS += ['django_rq']
```

### Huey

Lightweight alternative with minimal dependencies. Can run with Redis, SQLite, or in-memory.

```python
# pip install huey

# settings/base.py
HUEY = {
    'huey_class': 'huey.RedisHuey',
    'name': 'project_name',
    'url': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
    'immediate': env.bool('HUEY_IMMEDIATE', default=False),  # True for dev (runs inline)
    'consumer': {
        'workers': 4,
        'worker_type': 'thread',
    },
}

INSTALLED_APPS += ['huey.contrib.djhuey']
```

### Django-native Async (No Queue)

For simple cases, Django's async views and `asyncio` can handle lightweight background work without a separate task queue. This approach is limited: tasks do not survive server restarts, there is no retry mechanism, and you lose visibility into task status. Use it only for fire-and-forget work where failure is acceptable.

```python
import asyncio
from django.http import JsonResponse


async def submit_essay(request):
    essay = await sync_to_async(Essay.objects.create)(
        **form.cleaned_data
    )
    # Fire and forget: send notification without blocking response
    asyncio.create_task(notify_editors_async(essay))
    return JsonResponse({'id': str(essay.id)})
```

## Task Design Principles

### Idempotency

Tasks should be safe to run multiple times with the same arguments. Network failures, worker crashes, and retry logic all mean a task might execute more than once.

```python
# BAD: Not idempotent. Running twice sends two emails.
@app.task
def send_publish_notification(essay_id):
    essay = Essay.objects.get(pk=essay_id)
    send_email(essay.created_by.email, f'Your essay "{essay.title}" is live!')

# GOOD: Idempotent. Checks before acting.
@app.task
def send_publish_notification(essay_id):
    essay = Essay.objects.get(pk=essay_id)
    if essay.publish_notification_sent:
        return  # already done
    send_email(essay.created_by.email, f'Your essay "{essay.title}" is live!')
    essay.publish_notification_sent = True
    essay.save(update_fields=['publish_notification_sent'])
```

### Serializable Arguments

Pass IDs and simple values, not Django model instances. Model instances cannot be serialized to JSON, and even if they could, their data would be stale by the time the task runs.

```python
# BAD: Passing a model instance
@app.task
def serialize_essay(essay):
    essay.export_to_markdown()

# GOOD: Pass the ID, fetch fresh data in the task
@app.task
def serialize_essay(essay_id):
    try:
        essay = Essay.objects.get(pk=essay_id)
    except Essay.DoesNotExist:
        return  # object was deleted between enqueue and execution
    essay.export_to_markdown()
```

### Retry Strategy

```python
@app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # wait 60 seconds between retries
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,      # exponential backoff: 60s, 120s, 240s
    retry_jitter=True,       # add randomness to prevent thundering herd
)
def push_to_static_site(self, essay_id):
    try:
        essay = Essay.objects.get(pk=essay_id)
        client = GitHubClient()
        client.commit_file(
            path=f'content/essays/{essay.slug}.md',
            content=essay.to_markdown(),
        )
    except GitHubClient.ConnectionError as exc:
        raise self.retry(exc=exc)
```

### Task Timeouts

Always set time limits. A task without a timeout can block a worker forever.

```python
@app.task(
    time_limit=300,       # hard kill after 5 minutes
    soft_time_limit=240,  # raise SoftTimeLimitExceeded after 4 minutes
)
def generate_content_report(stage=None):
    try:
        report = build_content_report(stage=stage)
        save_report(report)
    except SoftTimeLimitExceeded:
        # Clean up and log that the report was too large
        logger.error('Report generation timed out for stage %s', stage)
        mark_report_failed(stage)
```

## Queue Architecture

### Priority Queues

Separate urgent tasks from bulk work.

```python
# Celery: route tasks to specific queues
CELERY_TASK_ROUTES = {
    'apps.notifications.tasks.send_urgent_alert': {'queue': 'high'},
    'apps.content.tasks.generate_monthly_report': {'queue': 'low'},
    'apps.content.tasks.serialize_*': {'queue': 'export'},
}

# Start workers for specific queues
# celery -A project_name worker -Q high -c 4
# celery -A project_name worker -Q default,low -c 2
```

### Dead Letter Queues

Tasks that fail after all retries need somewhere to go for investigation.

```python
@app.task(bind=True, max_retries=3)
def push_content_to_github(self, essay_id):
    try:
        result = github_api.commit_essay(essay_id)
        return result
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            # All retries exhausted: log for manual investigation
            FailedTask.objects.create(
                task_name='push_content_to_github',
                args={'essay_id': essay_id},
                exception=str(exc),
                failed_at=timezone.now(),
            )
            return
        raise self.retry(exc=exc)
```

## Periodic Tasks

### Celery Beat

```python
# pip install django-celery-beat

# settings/base.py
INSTALLED_APPS += ['django_celery_beat']

CELERY_BEAT_SCHEDULE = {
    'check-stale-drafts': {
        'task': 'apps.content.tasks.check_stale_drafts',
        'schedule': crontab(hour=8, minute=0),  # daily at 8 AM
    },
    'serialize-published-content': {
        'task': 'apps.content.tasks.serialize_all_published',
        'schedule': timedelta(minutes=15),
    },
    'cleanup-expired-sessions': {
        'task': 'apps.core.tasks.cleanup_sessions',
        'schedule': crontab(hour=3, minute=0, day_of_week='sunday'),
    },
}
```

### Django Management Commands as Scheduled Tasks

For simpler setups, cron + management commands work fine.

```python
# apps/content/management/commands/check_stale_drafts.py
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Check for essays stuck in drafting stage and notify editors'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report stale drafts without sending notifications',
        )

    def handle(self, *args, **options):
        stale = Essay.objects.stale_drafts()
        self.stdout.write(f'Found {stale.count()} stale drafts')

        if not options['dry_run']:
            for essay in stale:
                send_stale_draft_notification(essay)

        self.stdout.write(self.style.SUCCESS('Done'))
```

```bash
# crontab entry
0 8 * * * cd /app && python manage.py check_stale_drafts
```

## Testing Background Tasks

### Testing Celery Tasks Synchronously

```python
# settings/test.py
CELERY_TASK_ALWAYS_EAGER = True  # tasks run inline, not via broker
CELERY_TASK_EAGER_PROPAGATES = True  # exceptions propagate normally
```

```python
from unittest.mock import patch


class TestSendPublishNotification(TestCase):
    def test_sends_email_for_newly_published(self):
        essay = EssayFactory(publish_notification_sent=False)
        send_publish_notification(essay.id)
        essay.refresh_from_db()
        self.assertTrue(essay.publish_notification_sent)

    def test_skips_if_already_sent(self):
        essay = EssayFactory(publish_notification_sent=True)
        with patch('apps.notifications.tasks.send_email') as mock_send:
            send_publish_notification(essay.id)
            mock_send.assert_not_called()

    def test_handles_deleted_essay(self):
        # Task should not crash if the essay was deleted
        send_publish_notification(99999)  # non-existent ID
```

### Testing django-rq

```python
from django_rq import get_queue


class TestEssayExport(TestCase):
    def test_task_enqueues(self):
        queue = get_queue('default')
        queue.empty()

        serialize_essay.delay(self.essay.id)

        self.assertEqual(queue.count, 1)
        job = queue.jobs[0]
        self.assertEqual(job.args[0], self.essay.id)
```

## Monitoring

### Flower (Celery)

```bash
# pip install flower
# celery -A project_name flower --port=5555
```

Flower provides a web dashboard showing active workers, task throughput, failure rates, and individual task status.

### django-rq Dashboard

```python
# urls.py
urlpatterns = [
    path('admin/rq/', include('django_rq.urls')),
]
```

### Custom Task Monitoring

```python
import time
import logging

logger = logging.getLogger('tasks')


class TaskMonitorMixin:
    """Mixin for Celery tasks that logs execution time and status."""

    def __call__(self, *args, **kwargs):
        task_name = self.name
        start = time.monotonic()
        logger.info('Task started: %s args=%s', task_name, args)
        try:
            result = super().__call__(*args, **kwargs)
            duration = time.monotonic() - start
            logger.info('Task completed: %s (%.2fs)', task_name, duration)
            return result
        except Exception as exc:
            duration = time.monotonic() - start
            logger.error(
                'Task failed: %s (%.2fs) error=%s',
                task_name, duration, exc,
            )
            raise
```

## Decision Guide

| Need | Recommendation |
|------|---------------|
| Simple email sending | django-rq or Huey |
| Complex workflows with chaining | Celery |
| Periodic tasks with dynamic scheduling | Celery Beat |
| Minimal infrastructure | Huey with SQLite backend |
| Serverless deployment (Vercel, Lambda) | External queue service (SQS, Cloud Tasks) |
| Fire-and-forget with no durability | Django async views |
| Small internal tool | Management commands + cron |
