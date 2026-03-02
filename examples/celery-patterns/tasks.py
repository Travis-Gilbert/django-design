"""
Celery Task Patterns
====================

Task design patterns for a Django content publishing site.
Covers retry logic, binding, custom base classes, progress tracking,
external API calls, lifecycle handlers, and queue routing.

All tasks assume the content publishing domain:
- Essay, FieldNote, ShelfEntry, Project, VideoProject models
- Content stages: research, drafting, production, published
- Markdown rendering for a static site generator
"""

import logging
import time

import httpx
from celery import shared_task, Task
from celery.exceptions import SoftTimeLimitExceeded
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = get_task_logger(__name__)


# ===========================================================================
# Pattern 1: Simple shared_task with automatic retry
# ===========================================================================
# Use autoretry_for for transient errors. retry_backoff adds exponential
# delay between attempts (2s, 4s, 8s, ...) with jitter to avoid thundering
# herd problems.

@shared_task(
    autoretry_for=(httpx.TimeoutException, httpx.HTTPStatusError),
    retry_backoff=True,        # Exponential backoff: 2^retry_count seconds
    retry_backoff_max=600,     # Cap at 10 minutes
    retry_jitter=True,         # Add randomness to prevent thundering herd
    max_retries=5,
    acks_late=True,            # Acknowledge after completion, not on receive
)
def fetch_source_metadata(source_id: int) -> dict:
    """
    Fetch metadata for a research source from an external API.

    Retries automatically on timeout or HTTP errors with exponential backoff.
    Returns the metadata dict on success.
    """
    from apps.research.models import Source

    source = Source.objects.get(pk=source_id)

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{settings.METADATA_API_URL}/lookup",
            params={"url": source.url},
        )
        response.raise_for_status()
        metadata = response.json()

    # Update the source with fetched metadata.
    Source.objects.filter(pk=source_id).update(
        title=metadata.get("title", source.title),
        author=metadata.get("author", ""),
        published_date=metadata.get("published_date"),
        metadata_fetched_at=timezone.now(),
    )

    return metadata


# ===========================================================================
# Pattern 2: Bound task with manual self.retry()
# ===========================================================================
# bind=True gives access to `self` (the Task instance). Use this when you
# need fine-grained control over retry behavior, such as changing the
# countdown based on the exception type or modifying the task state.

@shared_task(bind=True, max_retries=3)
def render_essay_to_markdown(self, essay_id: int) -> str:
    """
    Render an essay's content to markdown for the static site generator.

    Uses bind=True for manual retry control. Different errors get different
    retry strategies.
    """
    from apps.content.models import Essay

    try:
        essay = Essay.objects.select_related("author").get(pk=essay_id)

        if essay.stage != "production":
            logger.warning(
                "Essay %s is in stage '%s', expected 'production'. Skipping.",
                essay.slug,
                essay.stage,
            )
            return ""

        # Update task state so callers can track progress.
        self.update_state(state="RENDERING", meta={"essay_slug": essay.slug})

        markdown_content = essay.render_to_markdown()

        Essay.objects.filter(pk=essay_id).update(
            rendered_markdown=markdown_content,
            rendered_at=timezone.now(),
        )

        return markdown_content

    except Essay.DoesNotExist:
        # Do not retry: the essay was deleted. Raise so the task fails.
        logger.error("Essay %d does not exist. Cannot render.", essay_id)
        raise

    except ConnectionError as exc:
        # Retry with increasing delay.
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))

    except SoftTimeLimitExceeded:
        # Clean up partial work before the hard limit kills us.
        logger.warning("Soft time limit hit rendering essay %d.", essay_id)
        Essay.objects.filter(pk=essay_id).update(
            render_error="Timed out during rendering",
        )
        raise


# ===========================================================================
# Pattern 3: Custom base class for error handling
# ===========================================================================
# Define a base class when multiple tasks share the same error handling,
# logging, or cleanup logic. This avoids repeating the same try/except
# in every task.

class ContentTaskBase(Task):
    """
    Base class for content processing tasks.

    Provides consistent error handling, logging, and model status updates.
    """

    # Do not store results by default for fire-and-forget tasks.
    ignore_result = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when a task fails after all retries are exhausted."""
        content_id = args[0] if args else kwargs.get("content_id")
        logger.error(
            "Task %s failed for content_id=%s: %s",
            self.name,
            content_id,
            exc,
            exc_info=einfo,
        )
        if content_id:
            self._mark_content_error(content_id, str(exc))

    def on_success(self, retval, task_id, args, kwargs):
        """Called when a task completes successfully."""
        content_id = args[0] if args else kwargs.get("content_id")
        logger.info(
            "Task %s succeeded for content_id=%s",
            self.name,
            content_id,
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called when a task is about to be retried."""
        content_id = args[0] if args else kwargs.get("content_id")
        logger.warning(
            "Task %s retrying for content_id=%s (attempt %d): %s",
            self.name,
            content_id,
            self.request.retries + 1,
            exc,
        )

    @staticmethod
    def _mark_content_error(content_id: int, error_message: str):
        """Mark a content item as having a processing error."""
        from apps.content.models import Essay

        Essay.objects.filter(pk=content_id).update(
            processing_error=error_message[:500],
            processing_failed_at=timezone.now(),
        )


@shared_task(
    base=ContentTaskBase,
    bind=True,
    autoretry_for=(httpx.TimeoutException,),
    max_retries=3,
    retry_backoff=True,
)
def process_essay_images(self, essay_id: int) -> int:
    """
    Process and optimize all images referenced in an essay.

    Uses ContentTaskBase for automatic error tracking in the database.
    Returns the number of images processed.
    """
    from apps.content.models import Essay, EssayImage

    essay = Essay.objects.get(pk=essay_id)
    images = EssayImage.objects.filter(essay=essay, processed=False)
    count = 0

    for image in images:
        # Resize, compress, upload to CDN.
        image.optimize()
        image.upload_to_cdn()
        image.processed = True
        image.save(update_fields=["processed"])
        count += 1

    return count


# ===========================================================================
# Pattern 4: Long-running task with progress tracking
# ===========================================================================
# Use self.update_state() with custom states to report progress.
# The caller can poll AsyncResult.state and AsyncResult.info to track it.
#
# Poll pattern (in a view or management command):
#     result = compile_project_bundle.delay(project_id)
#     while not result.ready():
#         info = result.info
#         if isinstance(info, dict):
#             print(f"{info['current']}/{info['total']} items processed")
#         time.sleep(2)

@shared_task(
    bind=True,
    soft_time_limit=540,  # 9 minutes
    time_limit=600,       # 10 minutes
)
def compile_project_bundle(self, project_id: int) -> dict:
    """
    Compile all content items in a project into a deployable bundle.

    Reports progress as a fraction so callers can display a progress bar.
    """
    from apps.content.models import Project

    project = Project.objects.prefetch_related("essays", "field_notes").get(
        pk=project_id,
    )

    items = list(project.essays.filter(stage="published")) + list(
        project.field_notes.filter(stage="published")
    )
    total = len(items)

    if total == 0:
        return {"status": "empty", "total": 0}

    compiled = []

    for i, item in enumerate(items, start=1):
        # Report progress.
        self.update_state(
            state="COMPILING",
            meta={
                "current": i,
                "total": total,
                "percent": int((i / total) * 100),
                "current_item": item.slug,
            },
        )

        try:
            markdown = item.render_to_markdown()
            compiled.append({"slug": item.slug, "content": markdown})
        except SoftTimeLimitExceeded:
            # Save partial progress before we get killed.
            logger.warning(
                "Time limit approaching. Compiled %d/%d items for project %s.",
                i - 1,
                total,
                project.slug,
            )
            return {
                "status": "partial",
                "compiled": len(compiled),
                "total": total,
            }

    # Write the bundle.
    bundle_path = project.write_bundle(compiled)

    return {
        "status": "complete",
        "compiled": len(compiled),
        "total": total,
        "bundle_path": str(bundle_path),
    }


# ===========================================================================
# Pattern 5: External API call with timeout and circuit breaker
# ===========================================================================
# When calling external services, use httpx with explicit timeouts and
# cache the circuit breaker state to avoid hammering a downed service.

CIRCUIT_BREAKER_KEY = "circuit:metadata_api"
CIRCUIT_BREAKER_TIMEOUT = 300  # 5 minutes


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def fetch_and_link_source(self, source_id: int, content_type: str, content_slug: str):
    """
    Fetch external source metadata and create a SourceLink.

    Implements a simple circuit breaker using Django cache: if the external
    API has failed recently, skip the call and retry later.
    """
    from apps.research.models import Source, SourceLink

    # Check circuit breaker.
    if cache.get(CIRCUIT_BREAKER_KEY):
        logger.warning("Circuit breaker open for metadata API. Will retry later.")
        raise self.retry(countdown=CIRCUIT_BREAKER_TIMEOUT)

    source = Source.objects.get(pk=source_id)

    try:
        with httpx.Client(
            timeout=httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0),
        ) as client:
            response = client.get(
                f"{settings.METADATA_API_URL}/lookup",
                params={"url": source.url},
            )
            response.raise_for_status()
            metadata = response.json()

    except httpx.TimeoutException as exc:
        # Open the circuit breaker after repeated timeouts.
        if self.request.retries >= 2:
            cache.set(CIRCUIT_BREAKER_KEY, True, CIRCUIT_BREAKER_TIMEOUT)
            logger.error(
                "Metadata API timed out %d times. Circuit breaker opened.",
                self.request.retries + 1,
            )
        raise self.retry(exc=exc)

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code >= 500:
            raise self.retry(exc=exc)
        # 4xx errors are not retryable.
        logger.error("Metadata API returned %d for source %d.", exc.response.status_code, source_id)
        raise

    # Update source and create link in a single transaction.
    with transaction.atomic():
        Source.objects.filter(pk=source_id).update(
            title=metadata.get("title", source.title),
            metadata_fetched_at=timezone.now(),
        )

        SourceLink.objects.update_or_create(
            source=source,
            content_type=content_type,
            content_slug=content_slug,
            defaults={
                "relevance_score": metadata.get("relevance", 0.5),
                "linked_at": timezone.now(),
            },
        )


# ===========================================================================
# Pattern 6: Task with on_failure / on_success handlers (inline)
# ===========================================================================
# Instead of a base class, you can define handlers as standalone functions
# and wire them up in the decorator. Useful for one-off tasks.

def _on_publish_failure(self, exc, task_id, args, kwargs, einfo):
    """Notify editors when a publish task fails."""
    essay_id = args[0] if args else kwargs.get("essay_id")
    logger.error("Publish failed for essay %s: %s", essay_id, exc)
    # In production, send an email or Slack notification here.
    from apps.content.models import Essay
    Essay.objects.filter(pk=essay_id).update(
        stage="production",  # Roll back from "publishing" to "production"
        publish_error=str(exc)[:500],
    )


def _on_publish_success(self, retval, task_id, args, kwargs):
    """Clear any previous error flags on successful publish."""
    essay_id = args[0] if args else kwargs.get("essay_id")
    from apps.content.models import Essay
    Essay.objects.filter(pk=essay_id).update(
        publish_error="",
        published_at=timezone.now(),
    )


@shared_task(
    bind=True,
    on_failure=_on_publish_failure,
    on_success=_on_publish_success,
    max_retries=2,
    soft_time_limit=120,
)
def publish_essay(self, essay_id: int) -> str:
    """
    Publish an essay: render markdown, upload assets, update stage.

    Uses inline on_failure/on_success handlers for lifecycle management.
    """
    from apps.content.models import Essay

    essay = Essay.objects.get(pk=essay_id)

    # Mark as publishing (intermediate state).
    Essay.objects.filter(pk=essay_id).update(stage="publishing")

    # Render and upload.
    markdown = essay.render_to_markdown()
    essay.upload_to_static_site(markdown)

    # Final stage update happens in on_success handler.
    Essay.objects.filter(pk=essay_id).update(stage="published")

    return essay.slug


# ===========================================================================
# Pattern 7: Task priority and explicit queue routing
# ===========================================================================
# Priority is set at call time with apply_async(), not in the decorator.
# Lower number = higher priority (0 is highest, 9 is lowest).
#
# Call examples:
#     # High-priority notification
#     send_publish_notification.apply_async(
#         args=[essay_id],
#         priority=0,
#         queue="notifications",
#     )
#
#     # Low-priority analytics
#     record_content_analytics.apply_async(
#         args=[essay_id],
#         priority=9,
#         queue="default",
#     )

@shared_task(ignore_result=True)
def send_publish_notification(essay_id: int):
    """
    Notify subscribers that an essay has been published.

    Called with high priority on the notifications queue.
    """
    from apps.content.models import Essay
    from apps.notifications.services import notify_subscribers

    essay = Essay.objects.get(pk=essay_id)
    notify_subscribers(
        event="essay_published",
        data={
            "title": essay.title,
            "slug": essay.slug,
            "author": essay.author.display_name,
        },
    )


@shared_task(ignore_result=True)
def record_content_analytics(essay_id: int, event_type: str = "view"):
    """
    Record an analytics event for a content item.

    Called with low priority on the default queue. Analytics should never
    block more important work.
    """
    from apps.content.models import Essay, ContentAnalytics

    essay = Essay.objects.get(pk=essay_id)
    ContentAnalytics.objects.create(
        content_slug=essay.slug,
        event_type=event_type,
        recorded_at=timezone.now(),
    )


# ===========================================================================
# Pattern 8: Idempotent task design
# ===========================================================================
# Tasks may be delivered more than once (at-least-once delivery).
# Design tasks so running them twice produces the same result.
# Use update_or_create, conditional updates, or idempotency keys.

@shared_task(
    autoretry_for=(Exception,),
    max_retries=3,
    retry_backoff=True,
    acks_late=True,
)
def sync_essay_to_search_index(essay_id: int):
    """
    Sync an essay to the search index. Safe to call multiple times.

    Idempotent: uses upsert logic (update_or_create) so duplicate
    deliveries do not create duplicate search entries.
    """
    from apps.content.models import Essay
    from apps.search.models import SearchEntry

    essay = Essay.objects.get(pk=essay_id)

    # update_or_create is naturally idempotent.
    SearchEntry.objects.update_or_create(
        content_type="essay",
        content_slug=essay.slug,
        defaults={
            "title": essay.title,
            "body_text": essay.plain_text_content,
            "author_name": essay.author.display_name,
            "published_at": essay.published_at,
            "updated_at": timezone.now(),
        },
    )
