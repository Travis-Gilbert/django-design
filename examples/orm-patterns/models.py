"""
ORM Pattern: Model Design
=========================

Demonstrates well-structured Django models for a content publishing site.
Covers abstract base models, field choices, indexes, constraints, custom
managers, model methods, and Django 5.x features like GeneratedField.

Domain: Publishing API with Essay, Tag, and supporting models.
"""

import uuid
from django.conf import settings
from django.db import models
from django.db.models import UniqueConstraint, CheckConstraint, Q
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


# ---------------------------------------------------------------------------
# Abstract Base Models
# ---------------------------------------------------------------------------

class TimestampedModel(models.Model):
    """
    Abstract base providing created/updated timestamps.

    Every model in the publishing system inherits from this. The updated_at
    field uses auto_now so it tracks the last save without manual intervention.
    """

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublishableModel(TimestampedModel):
    """
    Abstract base for content that moves through a publishing pipeline.

    Adds stage tracking, publication date, and a published() manager method.
    Subclasses define their own fields but get the full lifecycle for free.
    """

    class Stage(models.TextChoices):
        RESEARCH = "research", "Research"
        DRAFTING = "drafting", "Drafting"
        EDITING = "editing", "Editing"
        PRODUCTION = "production", "Production"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    stage = models.CharField(
        max_length=20,
        choices=Stage.choices,
        default=Stage.RESEARCH,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    def publish(self):
        """Transition content to published stage with timestamp."""
        self.stage = self.Stage.PUBLISHED
        self.published_at = timezone.now()
        self.save(update_fields=["stage", "published_at", "updated_at"])

    def is_published(self):
        return self.stage == self.Stage.PUBLISHED

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Tag (related model with M2M)
# ---------------------------------------------------------------------------

class Tag(TimestampedModel):
    """
    Tags shared across all content types.

    Uses a case-insensitive unique constraint so "Django" and "django"
    cannot coexist. The slug is the canonical lowercase form.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["name"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="tag_unique_name_ci",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Custom Manager and QuerySet (inline, see querysets.py for full version)
# ---------------------------------------------------------------------------

class EssayQuerySet(models.QuerySet):
    """Chainable queryset methods for Essay filtering."""

    def published(self):
        return self.filter(stage=PublishableModel.Stage.PUBLISHED)

    def drafts(self):
        return self.filter(stage__in=[
            PublishableModel.Stage.DRAFTING,
            PublishableModel.Stage.EDITING,
        ])

    def by_author(self, user):
        return self.filter(author=user)

    def recent(self, days=30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(published_at__gte=cutoff)

    def featured(self):
        return self.filter(is_featured=True, stage=PublishableModel.Stage.PUBLISHED)


class EssayManager(models.Manager):
    """
    Custom manager that exposes EssayQuerySet methods at the manager level.

    Usage:
        Essay.objects.published()
        Essay.objects.by_author(user).recent()
    """

    def get_queryset(self):
        return EssayQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def drafts(self):
        return self.get_queryset().drafts()

    def by_author(self, user):
        return self.get_queryset().by_author(user)

    def recent(self, days=30):
        return self.get_queryset().recent(days)

    def featured(self):
        return self.get_queryset().featured()


# ---------------------------------------------------------------------------
# Essay (primary content model)
# ---------------------------------------------------------------------------

class Essay(PublishableModel):
    """
    Long-form written content in the publishing system.

    Demonstrates:
    - Field choices via TextChoices
    - Custom manager with chainable queryset
    - Database-level constraints (word count, slug uniqueness)
    - Composite indexes for common query patterns
    - GeneratedField for computed columns (Django 5.x)
    - Model methods and properties
    - Proper __str__ and get_absolute_url
    """

    class ContentType(models.TextChoices):
        ESSAY = "essay", "Essay"
        TUTORIAL = "tutorial", "Tutorial"
        CASE_STUDY = "case_study", "Case Study"
        OPINION = "opinion", "Opinion"

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    subtitle = models.CharField(max_length=500, blank=True, default="")

    # Relationships
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="essays",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="essays")

    # Content
    body = models.TextField()
    excerpt = models.TextField(
        blank=True,
        default="",
        help_text="Short summary for listings and SEO. Auto-generated if blank.",
    )
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices,
        default=ContentType.ESSAY,
    )

    # Metadata
    word_count = models.PositiveIntegerField(default=0, editable=False)
    reading_time_minutes = models.PositiveSmallIntegerField(
        default=0,
        editable=False,
        help_text="Estimated reading time at 250 words per minute.",
    )
    is_featured = models.BooleanField(default=False, db_index=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible metadata: seo_title, og_image, canonical_url, etc.",
    )

    # Django 5.x GeneratedField: computed column stored in the database.
    # This keeps the search_vector in sync without triggers or signals.
    # Requires PostgreSQL for SearchVector; for other backends, use a
    # regular field updated in save().
    #
    # search_headline = models.GeneratedField(
    #     expression=Lower("title"),
    #     output_field=models.CharField(max_length=255),
    #     db_persist=True,
    # )
    #
    # A simpler GeneratedField example that works on all backends:
    slug_prefix = models.GeneratedField(
        expression=models.functions.Substr("slug", 1, 50),
        output_field=models.CharField(max_length=50),
        db_persist=True,
    )

    # Managers
    objects = EssayManager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name_plural = "essays"

        indexes = [
            # Composite index for the most common listing query:
            # published essays ordered by date
            models.Index(
                fields=["stage", "-published_at"],
                name="essay_published_listing",
                condition=Q(stage="published"),
            ),
            # Index for author dashboard queries
            models.Index(
                fields=["author", "stage", "-updated_at"],
                name="essay_author_dashboard",
            ),
            # GIN index for JSONB metadata lookups (PostgreSQL)
            # models.Index(
            #     fields=["metadata"],
            #     name="essay_metadata_gin",
            #     opclasses=["jsonb_path_ops"],
            # ),
        ]

        constraints = [
            # Ensure word count is non-negative
            CheckConstraint(
                check=Q(word_count__gte=0),
                name="essay_word_count_non_negative",
            ),
            # Published essays must have a published_at date
            CheckConstraint(
                check=~Q(stage="published") | Q(published_at__isnull=False),
                name="essay_published_has_date",
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("essays:detail", kwargs={"slug": self.slug})

    def save(self, *args, **kwargs):
        # Auto-generate slug from title
        if not self.slug:
            self.slug = slugify(self.title)

        # Compute word count and reading time
        if self.body:
            words = len(self.body.split())
            self.word_count = words
            self.reading_time_minutes = max(1, words // 250)

        # Auto-generate excerpt from body
        if not self.excerpt and self.body:
            self.excerpt = self.body[:300].rsplit(" ", 1)[0] + "..."

        super().save(*args, **kwargs)

    @property
    def is_long_form(self):
        """Essays over 2000 words are considered long-form."""
        return self.word_count > 2000

    @property
    def tag_list(self):
        """Comma-separated tag names, useful in templates and serializers."""
        return ", ".join(self.tags.values_list("name", flat=True))

    def next_stage(self):
        """
        Advance to the next stage in the publishing pipeline.
        Returns the new stage or None if already at the end.
        """
        stages = list(self.Stage)
        try:
            current_index = stages.index(self.Stage(self.stage))
        except ValueError:
            return None
        if current_index < len(stages) - 1:
            self.stage = stages[current_index + 1].value
            if self.stage == self.Stage.PUBLISHED:
                self.published_at = timezone.now()
            self.save(update_fields=["stage", "published_at", "updated_at"])
            return self.stage
        return None


# ---------------------------------------------------------------------------
# FieldNote (lightweight content model)
# ---------------------------------------------------------------------------

class FieldNote(PublishableModel):
    """
    Short-form observations and notes. Lighter weight than Essay.

    Demonstrates a simpler model that reuses the PublishableModel base
    without all the complexity of Essay.
    """

    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    body = models.TextField()
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="field_notes",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="field_notes")
    related_essay = models.ForeignKey(
        Essay,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="field_notes",
        help_text="Optional link to a parent essay this note supports.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
