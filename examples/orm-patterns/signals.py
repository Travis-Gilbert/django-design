"""
ORM Pattern: Signals
=====================

Demonstrates Django signal patterns for the content publishing domain.
Covers post_save, pre_save, and m2m_changed signals with proper
dispatch_uid, connection patterns, and a comparison to django-lifecycle.

Signals are useful for decoupled side effects but should be used sparingly.
When the side effect is tightly coupled to the model, consider overriding
save() or using django-lifecycle hooks instead.

All examples assume the models defined in models.py (Essay, Tag, FieldNote).
"""

import logging

from django.core.cache import cache
from django.db import models
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from django.utils.text import slugify

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# pre_save: Auto-populate slug before saving
# ---------------------------------------------------------------------------

@receiver(
    pre_save,
    sender="orm_patterns.Essay",
    dispatch_uid="essay_auto_slug",
)
def auto_populate_essay_slug(sender, instance, **kwargs):
    """
    Generate a slug from the title if one is not already set.

    Uses dispatch_uid to prevent duplicate signal connections, which can
    happen if the app is loaded more than once (common in testing and
    some deployment configurations).

    Why pre_save instead of save() override:
    - Works even when the model is saved via bulk operations that call
      save() on each instance (but NOT bulk_create/bulk_update, which
      skip signals entirely).
    - Keeps the slug logic separate from other save() concerns.

    When to use save() override instead:
    - When you need the logic to run on every save path including
      bulk operations you control.
    - When the logic is core to the model's identity, not a side effect.
    """
    if not instance.slug and instance.title:
        base_slug = slugify(instance.title)
        slug = base_slug
        counter = 1

        # Handle slug uniqueness. In high-concurrency scenarios, consider
        # a database-level unique constraint with retry logic instead.
        while sender.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        instance.slug = slug


# ---------------------------------------------------------------------------
# post_save: Side effects after successful save
# ---------------------------------------------------------------------------

@receiver(
    post_save,
    sender="orm_patterns.Essay",
    dispatch_uid="essay_post_save_notify",
)
def handle_essay_saved(sender, instance, created, **kwargs):
    """
    Perform side effects after an essay is saved.

    The `created` flag distinguishes between new records and updates.
    The `update_fields` kwarg tells you which fields were updated
    (None means all fields were saved).

    Important: This signal runs inside the same database transaction as
    the save(). If you need to guarantee the data is committed before
    running side effects, use transaction.on_commit().
    """
    from django.db import transaction

    update_fields = kwargs.get("update_fields")

    if created:
        logger.info("New essay created: %s (id=%s)", instance.title, instance.pk)

        # Schedule async notification using on_commit to ensure the
        # essay is committed to the database before the Celery task
        # tries to read it.
        transaction.on_commit(
            lambda: _schedule_new_essay_notification(instance.pk)
        )

    elif update_fields and "stage" in update_fields:
        # Only react to stage changes, not every save
        if instance.stage == "published":
            logger.info("Essay published: %s", instance.title)
            transaction.on_commit(
                lambda: _invalidate_essay_caches(instance)
            )


def _schedule_new_essay_notification(essay_pk):
    """
    Placeholder for scheduling an async task.
    In production, this would call a Celery task:

        from apps.content.tasks import notify_new_essay
        notify_new_essay.delay(essay_pk)
    """
    logger.info("Scheduling notification for essay pk=%s", essay_pk)


def _invalidate_essay_caches(essay):
    """Invalidate caches related to the published essay."""
    cache_keys = [
        f"essay:{essay.slug}",
        f"essay_list:published",
        f"author:{essay.author_id}:essays",
        "homepage:featured_essays",
    ]
    cache.delete_many(cache_keys)
    logger.info("Invalidated %d cache keys for essay %s", len(cache_keys), essay.slug)


# ---------------------------------------------------------------------------
# m2m_changed: React to Many-to-Many relationship changes
# ---------------------------------------------------------------------------

@receiver(
    m2m_changed,
    sender="orm_patterns.Essay.tags.through",  # The intermediary table
    dispatch_uid="essay_tags_changed",
)
def handle_essay_tags_changed(sender, instance, action, pk_set, **kwargs):
    """
    React when tags are added to or removed from an essay.

    The m2m_changed signal fires multiple times during a single M2M operation:
    - pre_add / post_add: Before/after tags are added
    - pre_remove / post_remove: Before/after tags are removed
    - pre_clear / post_clear: Before/after all tags are removed

    We only act on post_* actions to avoid interfering with the operation
    and to ensure the database state is consistent.

    Parameters:
    - instance: The Essay that was modified
    - action: One of 'pre_add', 'post_add', 'pre_remove', 'post_remove',
              'pre_clear', 'post_clear'
    - pk_set: Set of Tag PKs being added/removed (None for clear actions)
    """
    if action == "post_add" and pk_set:
        logger.info(
            "Tags added to essay '%s': %s",
            instance.title,
            list(pk_set),
        )
        # Invalidate tag-based caches
        _invalidate_tag_caches(pk_set)

    elif action == "post_remove" and pk_set:
        logger.info(
            "Tags removed from essay '%s': %s",
            instance.title,
            list(pk_set),
        )
        _invalidate_tag_caches(pk_set)

    elif action == "post_clear":
        logger.info("All tags cleared from essay '%s'", instance.title)
        cache.delete(f"essay:{instance.slug}:tags")


def _invalidate_tag_caches(tag_pks):
    """Invalidate caches for specific tags."""
    cache_keys = [f"tag:{pk}:essays" for pk in tag_pks]
    cache_keys.append("tags:popular")
    cache.delete_many(cache_keys)


# ---------------------------------------------------------------------------
# Signal connection in AppConfig.ready()
# ---------------------------------------------------------------------------

"""
IMPORTANT: Where to connect signals.

Option 1: Decorators (shown above)
    Use @receiver decorators in a signals.py file and import it from
    your AppConfig.ready() method.

Option 2: Manual connection in AppConfig.ready()
    Connect signals programmatically. This is more explicit and avoids
    import side effects.

Example AppConfig:

    # apps/content/apps.py
    from django.apps import AppConfig

    class ContentConfig(AppConfig):
        default_auto_field = "django.db.models.BigAutoField"
        name = "apps.content"

        def ready(self):
            # Import the signals module so decorators register
            import apps.content.signals  # noqa: F401

            # Or connect manually:
            # from django.db.models.signals import post_save
            # from apps.content.models import Essay
            # from apps.content.signals import handle_essay_saved
            # post_save.connect(
            #     handle_essay_saved,
            #     sender=Essay,
            #     dispatch_uid="essay_post_save_notify",
            # )
"""


# ---------------------------------------------------------------------------
# django-lifecycle as a Cleaner Alternative
# ---------------------------------------------------------------------------

"""
COMPARISON: django-lifecycle hooks vs Django signals

django-lifecycle (https://github.com/rsinger86/django-lifecycle) provides
decorator-based hooks that live directly on the model. This collocates
the trigger logic with the model definition, making it easier to follow.

Install: pip install django-lifecycle

The same patterns shown above with signals, rewritten as lifecycle hooks:

    from django_lifecycle import LifecycleModel, hook, AFTER_CREATE, AFTER_UPDATE, BEFORE_SAVE

    class Essay(LifecycleModel, PublishableModel):
        # ... fields ...

        @hook(BEFORE_SAVE, when="title", has_changed=True)
        def auto_slug(self):
            \"\"\"Generate slug when title changes. Replaces pre_save signal.\"\"\"
            if not self.slug:
                self.slug = slugify(self.title)

        @hook(AFTER_CREATE)
        def on_create(self):
            \"\"\"Notify on creation. Replaces post_save with created=True.\"\"\"
            from django.db import transaction
            transaction.on_commit(
                lambda: _schedule_new_essay_notification(self.pk)
            )

        @hook(AFTER_UPDATE, when="stage", was="editing", is_now="published")
        def on_publish(self):
            \"\"\"
            React to publishing. Replaces post_save with field checking.

            The key advantage: `when`, `was`, and `is_now` let you express
            state transitions declaratively. With signals, you have to
            track the previous value yourself.
            \"\"\"
            from django.db import transaction
            transaction.on_commit(
                lambda: _invalidate_essay_caches(self)
            )

        @hook(AFTER_UPDATE, when="stage", is_now="archived")
        def on_archive(self):
            \"\"\"Additional hook for archiving. Easy to add without touching
            existing hooks.\"\"\"
            logger.info("Essay archived: %s", self.title)

When to use signals vs lifecycle hooks:

    Signals are better when:
    - The side effect is in a different app from the model
    - You need loose coupling between apps
    - The model is from a third-party package you cannot modify
    - You need m2m_changed behavior (lifecycle does not cover M2M)

    Lifecycle hooks are better when:
    - The side effect is closely related to the model
    - You need to react to specific field transitions (was X, is now Y)
    - You want the logic visible in the model definition
    - You want to avoid the indirection and debugging difficulty of signals

Both approaches have the same limitation: they do not fire for bulk_create(),
bulk_update(), or raw SQL updates. For those cases, use database triggers
or scheduled tasks.
"""
