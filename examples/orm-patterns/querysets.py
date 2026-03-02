"""
ORM Pattern: QuerySets and Managers
====================================

Demonstrates advanced queryset patterns for the content publishing domain.
Covers custom QuerySet classes, chainable methods, annotations, aggregations,
subqueries, prefetching, window functions, and bulk operations.

All examples assume the models defined in models.py (Essay, Tag, FieldNote).
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import (
    Avg,
    Case,
    Count,
    Exists,
    F,
    Max,
    Min,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import (
    Coalesce,
    ExtractMonth,
    ExtractYear,
    Length,
    Now,
    Rank,
    RowNumber,
    TruncMonth,
)
from django.utils import timezone


# ---------------------------------------------------------------------------
# Custom QuerySet with Chainable Methods
# ---------------------------------------------------------------------------

class EssayQuerySet(models.QuerySet):
    """
    Chainable queryset methods for Essay.

    Design principle: each method does one thing and returns a queryset,
    so callers can compose them freely.

    Usage:
        Essay.objects.published().by_author(user).recent()
        Essay.objects.featured().with_tag_counts()
    """

    # --- Filtering ---

    def published(self):
        """Only published essays with a publication date."""
        return self.filter(
            stage="published",
            published_at__isnull=False,
        )

    def drafts(self):
        """Essays in drafting or editing stages."""
        return self.filter(stage__in=["drafting", "editing"])

    def by_author(self, user):
        """Filter to a specific author."""
        return self.filter(author=user)

    def by_content_type(self, content_type):
        """Filter by content type (essay, tutorial, case_study, opinion)."""
        return self.filter(content_type=content_type)

    def recent(self, days=30):
        """Published within the last N days."""
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(published_at__gte=cutoff)

    def featured(self):
        """Published and marked as featured."""
        return self.filter(is_featured=True, stage="published")

    def long_form(self, min_words=2000):
        """Essays above a word count threshold."""
        return self.filter(word_count__gte=min_words)

    def with_tag(self, tag_slug):
        """Essays that have a specific tag."""
        return self.filter(tags__slug=tag_slug)

    def search(self, query):
        """
        Basic text search across title, subtitle, and body.
        For production, use PostgreSQL full-text search or a dedicated
        search engine (Elasticsearch, Meilisearch).
        """
        return self.filter(
            Q(title__icontains=query)
            | Q(subtitle__icontains=query)
            | Q(body__icontains=query)
        )

    # --- Annotations ---

    def with_tag_counts(self):
        """Annotate each essay with its tag count."""
        return self.annotate(tag_count=Count("tags"))

    def with_field_note_counts(self):
        """Annotate each essay with the number of related field notes."""
        return self.annotate(note_count=Count("field_notes"))

    def with_reading_category(self):
        """
        Annotate with a human-readable reading length category.
        Uses Case/When for conditional logic in the database.
        """
        return self.annotate(
            reading_category=Case(
                When(word_count__lt=500, then=Value("quick read")),
                When(word_count__lt=1500, then=Value("standard")),
                When(word_count__lt=3000, then=Value("long form")),
                default=Value("deep dive"),
                output_field=models.CharField(),
            )
        )

    # --- Optimization ---

    def with_author(self):
        """Select-related on author to avoid N+1 on listings."""
        return self.select_related("author")

    def with_tags(self):
        """Prefetch tags for efficient M2M access."""
        return self.prefetch_related("tags")

    def for_listing(self):
        """
        Optimized queryset for essay listing pages.
        Combines select_related, prefetch_related, and deferred fields.
        """
        return (
            self.select_related("author")
            .prefetch_related("tags")
            .defer("body", "metadata")  # Skip heavy fields for listings
        )

    def for_detail(self):
        """Full queryset for essay detail pages."""
        return (
            self.select_related("author")
            .prefetch_related(
                "tags",
                Prefetch(
                    "field_notes",
                    queryset=(
                        # Import would be circular in real code; shown inline
                        # for pattern demonstration
                        self.model.field_notes.rel.related_model.objects
                        .filter(stage="published")
                        .select_related("author")
                        .order_by("-created_at")[:5]
                    ),
                    to_attr="recent_notes",
                ),
            )
        )


class EssayManager(models.Manager):
    """
    Manager that delegates to EssayQuerySet.

    The from_queryset() shortcut auto-generates manager methods for every
    queryset method. This is the recommended approach when you want all
    queryset methods available on the manager.
    """

    def get_queryset(self):
        return EssayQuerySet(self.model, using=self._db)

    # Expose commonly used filters directly on the manager
    def published(self):
        return self.get_queryset().published()

    def drafts(self):
        return self.get_queryset().drafts()

    def featured(self):
        return self.get_queryset().featured()


# Alternative: use from_queryset() to auto-create the manager.
# This generates a manager class with all EssayQuerySet methods.
#
# EssayManager = EssayQuerySet.as_manager()
#   -- or --
# EssayManager = models.Manager.from_queryset(EssayQuerySet)


# ---------------------------------------------------------------------------
# Annotation and Aggregation Patterns
# ---------------------------------------------------------------------------

def author_statistics(user):
    """
    Aggregate statistics for an author's essays.

    Returns a dictionary with counts, averages, and date ranges.
    """
    from .models import Essay  # Local import to avoid circular dependency

    return Essay.objects.by_author(user).aggregate(
        total_essays=Count("id"),
        published_count=Count("id", filter=Q(stage="published")),
        draft_count=Count("id", filter=Q(stage__in=["drafting", "editing"])),
        avg_word_count=Avg("word_count"),
        total_words=Sum("word_count"),
        longest_essay=Max("word_count"),
        shortest_published=Min(
            "word_count",
            filter=Q(stage="published"),
        ),
        first_published=Min("published_at"),
        last_published=Max("published_at"),
    )


def monthly_publishing_stats():
    """
    Group published essays by month with counts and average word counts.
    Uses TruncMonth for date truncation.
    """
    from .models import Essay

    return (
        Essay.objects
        .published()
        .annotate(month=TruncMonth("published_at"))
        .values("month")
        .annotate(
            count=Count("id"),
            avg_words=Avg("word_count"),
            total_words=Sum("word_count"),
        )
        .order_by("-month")
    )


def top_tags(limit=10):
    """
    Tags ranked by number of published essays.
    Uses annotation + ordering for a top-N query.
    """
    from .models import Tag

    return (
        Tag.objects
        .annotate(
            essay_count=Count(
                "essays",
                filter=Q(essays__stage="published"),
            )
        )
        .filter(essay_count__gt=0)
        .order_by("-essay_count")[:limit]
    )


# ---------------------------------------------------------------------------
# Subquery and OuterRef Patterns
# ---------------------------------------------------------------------------

def essays_with_latest_note_date():
    """
    Annotate each essay with the date of its most recent field note.
    Uses Subquery + OuterRef to correlate the subquery to each essay row.
    """
    from .models import Essay, FieldNote

    latest_note = (
        FieldNote.objects
        .filter(related_essay=OuterRef("pk"))
        .order_by("-created_at")
        .values("created_at")[:1]
    )

    return Essay.objects.annotate(
        latest_note_date=Subquery(latest_note)
    )


def essays_with_note_existence():
    """
    Annotate essays with a boolean indicating whether they have any
    published field notes. Exists() is more efficient than Count() > 0
    because the database can stop at the first match.
    """
    from .models import Essay, FieldNote

    has_notes = FieldNote.objects.filter(
        related_essay=OuterRef("pk"),
        stage="published",
    )

    return Essay.objects.annotate(has_notes=Exists(has_notes))


def essays_with_author_total():
    """
    Annotate each essay with its author's total published essay count.
    Shows a correlated subquery referencing a different relationship.
    """
    from .models import Essay

    author_total = (
        Essay.objects
        .filter(
            author=OuterRef("author"),
            stage="published",
        )
        .values("author")
        .annotate(cnt=Count("id"))
        .values("cnt")[:1]
    )

    return Essay.objects.annotate(
        author_essay_count=Coalesce(Subquery(author_total), 0)
    )


# ---------------------------------------------------------------------------
# Select Related and Prefetch Related Optimization
# ---------------------------------------------------------------------------

def optimized_essay_list():
    """
    Demonstrates the difference between naive and optimized queries.

    BAD (N+1 queries):
        essays = Essay.objects.all()
        for essay in essays:
            print(essay.author.username)  # Extra query per essay
            print(essay.tags.all())        # Extra query per essay

    GOOD (3 queries total):
        essays = Essay.objects.select_related('author').prefetch_related('tags')
        for essay in essays:
            print(essay.author.username)  # No extra query
            print(essay.tags.all())        # No extra query
    """
    from .models import Essay, FieldNote

    return (
        Essay.objects
        .select_related("author")  # FK: single JOIN
        .prefetch_related(
            "tags",  # M2M: separate query, cached
            Prefetch(
                "field_notes",
                queryset=FieldNote.objects.filter(
                    stage="published",
                ).only("title", "slug", "created_at"),
                to_attr="published_notes",  # List, not QuerySet
            ),
        )
        .published()
        .order_by("-published_at")
    )


def filtered_prefetch_example(user):
    """
    Prefetch with a filtered queryset: only load the user's own
    field notes for each essay, not everyone's.
    """
    from .models import Essay, FieldNote

    user_notes = Prefetch(
        "field_notes",
        queryset=FieldNote.objects.filter(author=user).order_by("-created_at"),
        to_attr="my_notes",
    )

    return (
        Essay.objects
        .published()
        .prefetch_related(user_notes, "tags")
        .select_related("author")
    )


# ---------------------------------------------------------------------------
# Window Functions
# ---------------------------------------------------------------------------

def essays_with_rank():
    """
    Rank essays by word count within each content type.
    Window functions run calculations across a set of rows related to
    the current row without collapsing them (unlike GROUP BY).
    """
    from .models import Essay

    return (
        Essay.objects
        .published()
        .annotate(
            rank_in_type=Window(
                expression=Rank(),
                partition_by=F("content_type"),
                order_by=F("word_count").desc(),
            ),
            row_num=Window(
                expression=RowNumber(),
                order_by=F("published_at").desc(),
            ),
        )
    )


def essays_with_running_word_total():
    """
    Running total of words published, ordered by publication date.
    Useful for dashboards showing cumulative output over time.
    """
    from .models import Essay

    return (
        Essay.objects
        .published()
        .annotate(
            cumulative_words=Window(
                expression=Sum("word_count"),
                order_by=F("published_at").asc(),
            )
        )
        .order_by("published_at")
    )


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------

def bulk_create_tags(tag_names):
    """
    Create multiple tags in a single INSERT statement.
    ignore_conflicts=True skips duplicates instead of raising IntegrityError.
    """
    from django.utils.text import slugify
    from .models import Tag

    tags = [
        Tag(name=name, slug=slugify(name))
        for name in tag_names
    ]

    return Tag.objects.bulk_create(
        tags,
        ignore_conflicts=True,  # Skip if slug already exists
        batch_size=500,  # Process in batches of 500
    )


def bulk_update_word_counts():
    """
    Recalculate word counts for all essays in bulk.

    Pattern:
    1. Fetch essays with the fields you need
    2. Modify in Python
    3. Bulk update only the changed fields

    bulk_update is much faster than saving each object individually
    because it uses a single UPDATE statement (or batched UPDATEs).
    """
    from .models import Essay

    essays = Essay.objects.only("id", "body", "word_count")
    updated = []

    for essay in essays.iterator(chunk_size=500):
        new_count = len(essay.body.split()) if essay.body else 0
        if essay.word_count != new_count:
            essay.word_count = new_count
            essay.reading_time_minutes = max(1, new_count // 250)
            updated.append(essay)

    if updated:
        Essay.objects.bulk_update(
            updated,
            fields=["word_count", "reading_time_minutes"],
            batch_size=500,
        )

    return len(updated)


def bulk_archive_old_drafts(days=365):
    """
    Archive drafts that have not been updated in over a year.

    Uses update() for a single SQL UPDATE statement. This is faster than
    fetching objects and saving them, but it skips model save() and signals.
    """
    from .models import Essay

    cutoff = timezone.now() - timedelta(days=days)

    count = (
        Essay.objects
        .filter(
            stage__in=["research", "drafting"],
            updated_at__lt=cutoff,
        )
        .update(stage="archived")
    )

    return count


# ---------------------------------------------------------------------------
# F Expressions for Atomic Updates
# ---------------------------------------------------------------------------

def increment_view_count(essay_id):
    """
    Atomic increment using F expression. Avoids race conditions because
    the increment happens in SQL, not in Python.

    BAD (race condition):
        essay = Essay.objects.get(id=essay_id)
        essay.view_count += 1  # Read-modify-write in Python
        essay.save()

    GOOD (atomic in SQL):
        Essay.objects.filter(id=essay_id).update(view_count=F('view_count') + 1)

    Note: view_count field not in our model; shown as a common pattern.
    """
    from .models import Essay

    Essay.objects.filter(id=essay_id).update(
        view_count=F("view_count") + 1,
    )


# ---------------------------------------------------------------------------
# Complex Filtering with Q Objects
# ---------------------------------------------------------------------------

def search_essays(query, author=None, tags=None, min_words=None):
    """
    Build a complex filter dynamically using Q objects.
    Each filter is optional and composable.
    """
    from .models import Essay

    filters = Q(stage="published")

    if query:
        filters &= (
            Q(title__icontains=query)
            | Q(subtitle__icontains=query)
            | Q(body__icontains=query)
        )

    if author:
        filters &= Q(author=author)

    if tags:
        # All tags must be present (AND logic for M2M)
        for tag_slug in tags:
            filters &= Q(tags__slug=tag_slug)

    if min_words:
        filters &= Q(word_count__gte=min_words)

    return (
        Essay.objects
        .filter(filters)
        .select_related("author")
        .prefetch_related("tags")
        .distinct()  # Needed when filtering on M2M with multiple values
        .order_by("-published_at")
    )
