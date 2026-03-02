"""
ORM Pattern: Advanced Lookups
==============================

Demonstrates complex lookup patterns for Django ORM queries in the
content publishing domain. Covers Q object composition, date-based
filtering, JSONField lookups, related field traversal, exclude patterns,
and Case/When conditional expressions.

All examples assume the models defined in models.py (Essay, Tag, FieldNote).
"""

from datetime import date, timedelta

from django.db.models import (
    Case,
    CharField,
    Count,
    F,
    IntegerField,
    Q,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    ExtractMonth,
    ExtractWeekDay,
    ExtractYear,
    Length,
    Now,
    Upper,
)
from django.utils import timezone


# ---------------------------------------------------------------------------
# Complex Q Object Combinations
# ---------------------------------------------------------------------------

def featured_or_recent_tutorials():
    """
    OR logic: featured essays OR tutorials published in the last 7 days.
    Parentheses in Q objects control precedence, just like in SQL.
    """
    from .models import Essay

    seven_days_ago = timezone.now() - timedelta(days=7)

    return Essay.objects.filter(
        Q(is_featured=True)
        | Q(
            content_type="tutorial",
            published_at__gte=seven_days_ago,
        )
    ).filter(
        stage="published",  # AND with the outer filter
    )


def complex_editorial_filter():
    """
    Nested Q objects for complex editorial logic.

    Find essays that are either:
    - Published tutorials with 1000+ words, OR
    - Featured essays of any type, OR
    - Drafts by a specific author that have been updated recently

    AND exclude:
    - Anything in the archived stage
    """
    from .models import Essay

    one_week_ago = timezone.now() - timedelta(days=7)

    editorial_filter = (
        Q(
            stage="published",
            content_type="tutorial",
            word_count__gte=1000,
        )
        | Q(
            stage="published",
            is_featured=True,
        )
        | Q(
            stage__in=["drafting", "editing"],
            updated_at__gte=one_week_ago,
        )
    ) & ~Q(stage="archived")

    return Essay.objects.filter(editorial_filter)


def dynamic_filter_builder(filters_dict):
    """
    Build Q objects dynamically from a dictionary of filter parameters.
    Useful for search APIs and admin views.

    Usage:
        results = dynamic_filter_builder({
            'author_username': 'jane',
            'content_type': 'tutorial',
            'min_words': 500,
            'tags': ['django', 'python'],
        })
    """
    from .models import Essay

    q = Q(stage="published")

    field_map = {
        "author_username": lambda v: Q(author__username=v),
        "content_type": lambda v: Q(content_type=v),
        "min_words": lambda v: Q(word_count__gte=v),
        "max_words": lambda v: Q(word_count__lte=v),
        "is_featured": lambda v: Q(is_featured=v),
        "search": lambda v: (
            Q(title__icontains=v)
            | Q(body__icontains=v)
        ),
    }

    for key, value in filters_dict.items():
        if key in field_map and value is not None:
            q &= field_map[key](value)
        elif key == "tags" and value:
            for tag in value:
                q &= Q(tags__slug=tag)

    return Essay.objects.filter(q).distinct()


# ---------------------------------------------------------------------------
# Date-Based Filtering
# ---------------------------------------------------------------------------

def published_this_year():
    """Filter by the current year using ExtractYear."""
    from .models import Essay

    current_year = timezone.now().year
    return Essay.objects.filter(
        published_at__year=current_year,
        stage="published",
    )


def published_in_range(start_date, end_date):
    """
    Filter by a date range. The __range lookup is inclusive on both ends.
    """
    from .models import Essay

    return Essay.objects.filter(
        published_at__range=(start_date, end_date),
        stage="published",
    )


def published_by_quarter():
    """
    Group essays by quarter using ExtractMonth with Case/When.
    """
    from .models import Essay

    return (
        Essay.objects
        .published()
        .annotate(
            quarter=Case(
                When(published_at__month__lte=3, then=Value("Q1")),
                When(published_at__month__lte=6, then=Value("Q2")),
                When(published_at__month__lte=9, then=Value("Q3")),
                default=Value("Q4"),
                output_field=CharField(),
            ),
            year=ExtractYear("published_at"),
        )
        .values("year", "quarter")
        .annotate(count=Count("id"))
        .order_by("year", "quarter")
    )


def stale_drafts(days=90):
    """
    Find drafts that have not been touched in N days.
    Uses F expression with Now() for database-side date arithmetic.
    """
    from .models import Essay

    return Essay.objects.filter(
        stage__in=["research", "drafting", "editing"],
        updated_at__lt=Now() - timedelta(days=days),
    )


def essays_updated_on_weekday(weekday=2):
    """
    Find essays last updated on a specific weekday (1=Sunday, 7=Saturday
    in Django's ExtractWeekDay, which follows the database convention).

    Monday = 2 in Django's weekday extraction.
    """
    from .models import Essay

    return Essay.objects.annotate(
        update_weekday=ExtractWeekDay("updated_at"),
    ).filter(update_weekday=weekday)


# ---------------------------------------------------------------------------
# JSONField Lookups
# ---------------------------------------------------------------------------

def essays_with_seo_title():
    """
    Check for a specific key in a JSONField.
    The __has_key lookup checks whether the key exists in the JSON object.
    """
    from .models import Essay

    return Essay.objects.filter(metadata__has_key="seo_title")


def essays_with_any_seo_field():
    """
    Check for any of several keys.
    __has_any_keys returns rows where at least one key is present.
    """
    from .models import Essay

    return Essay.objects.filter(
        metadata__has_any_keys=["seo_title", "og_image", "canonical_url"],
    )


def essays_with_all_seo_fields():
    """
    Check that all required keys are present.
    __has_keys requires every listed key to exist in the JSON.
    """
    from .models import Essay

    return Essay.objects.filter(
        metadata__has_keys=["seo_title", "og_image", "meta_description"],
    )


def essays_by_series(series_name):
    """
    Lookup a nested value inside a JSONField.
    Uses the __ path syntax to traverse JSON keys.

    Assumes metadata like: {"series": {"name": "Django Deep Dives", "part": 3}}
    """
    from .models import Essay

    return Essay.objects.filter(
        metadata__series__name=series_name,
        stage="published",
    ).order_by("metadata__series__part")


def essays_with_metadata_contains():
    """
    Find essays whose metadata contains specific key-value pairs.
    __contains does a superset check on the JSON structure.
    """
    from .models import Essay

    return Essay.objects.filter(
        metadata__contains={"featured_section": "homepage"},
    )


def essays_with_json_array_contains():
    """
    Filter by values inside a JSON array.

    Assumes metadata like: {"categories": ["tech", "django", "python"]}
    The __contains lookup with a list checks array inclusion.
    """
    from .models import Essay

    return Essay.objects.filter(
        metadata__categories__contains=["django"],
    )


# ---------------------------------------------------------------------------
# Related Field Traversal
# ---------------------------------------------------------------------------

def essays_by_author_email_domain(domain):
    """
    Traverse FK relationships using double-underscore syntax.
    This reaches through essay -> author -> email.
    """
    from .models import Essay

    return Essay.objects.filter(
        author__email__endswith=f"@{domain}",
        stage="published",
    )


def essays_with_published_notes():
    """
    Filter essays that have at least one published field note.
    Traverses the reverse FK relationship.
    """
    from .models import Essay

    return Essay.objects.filter(
        field_notes__stage="published",
    ).distinct()


def tags_used_in_tutorials():
    """
    Traverse M2M in the reverse direction: from Tag to Essay.
    Find tags that appear on at least one published tutorial.
    """
    from .models import Tag

    return Tag.objects.filter(
        essays__content_type="tutorial",
        essays__stage="published",
    ).distinct()


def essays_sharing_tags_with(essay):
    """
    Find essays that share at least one tag with the given essay.
    Useful for "related essays" features.
    """
    from .models import Essay

    shared_tags = essay.tags.values_list("id", flat=True)

    return (
        Essay.objects
        .filter(tags__id__in=shared_tags, stage="published")
        .exclude(pk=essay.pk)
        .annotate(shared_count=Count("tags", filter=Q(tags__id__in=shared_tags)))
        .order_by("-shared_count", "-published_at")
        .distinct()
    )


# ---------------------------------------------------------------------------
# Exclude Patterns
# ---------------------------------------------------------------------------

def essays_without_tags():
    """
    Find essays that have zero tags. Uses isnull on the M2M relationship.
    """
    from .models import Essay

    return Essay.objects.filter(tags__isnull=True)


def essays_excluding_content_types(excluded_types):
    """
    Exclude specific content types from results.
    The __in lookup combined with exclude() removes matching rows.
    """
    from .models import Essay

    return Essay.objects.published().exclude(
        content_type__in=excluded_types,
    )


def essays_without_field_notes():
    """
    Find published essays with no field notes at all.
    Exclude + isnull is the standard pattern for "has none of" queries.
    """
    from .models import Essay

    return Essay.objects.published().filter(
        field_notes__isnull=True,
    )


def essays_not_by_prolific_authors(min_essays=50):
    """
    Exclude essays by authors who have published more than N essays.
    Combines annotation with exclude for inverse filtering.
    """
    from .models import Essay

    prolific_authors = (
        Essay.objects
        .published()
        .values("author")
        .annotate(pub_count=Count("id"))
        .filter(pub_count__gte=min_essays)
        .values_list("author", flat=True)
    )

    return Essay.objects.published().exclude(
        author__in=prolific_authors,
    )


# ---------------------------------------------------------------------------
# Case/When Conditional Expressions
# ---------------------------------------------------------------------------

def essays_with_priority_score():
    """
    Compute a priority score in the database using Case/When.
    This avoids fetching all rows and scoring in Python.

    Scoring:
    - Featured: +10 points
    - Tutorial: +5 points
    - Long form (2000+ words): +3 points
    - Published in last 7 days: +7 points
    """
    from .models import Essay

    seven_days_ago = timezone.now() - timedelta(days=7)

    return (
        Essay.objects
        .published()
        .annotate(
            priority_score=(
                Case(
                    When(is_featured=True, then=Value(10)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(content_type="tutorial", then=Value(5)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(word_count__gte=2000, then=Value(3)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
                + Case(
                    When(published_at__gte=seven_days_ago, then=Value(7)),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
        )
        .order_by("-priority_score", "-published_at")
    )


def categorize_authors_by_output():
    """
    Categorize authors by their total output using Case/When on aggregates.
    Returns author info with a productivity label.
    """
    from .models import Essay

    return (
        Essay.objects
        .published()
        .values("author__username", "author__email")
        .annotate(
            essay_count=Count("id"),
            total_words=Coalesce(
                models.Sum("word_count"),
                0,
                output_field=IntegerField(),
            ),
        )
        .annotate(
            author_tier=Case(
                When(essay_count__gte=50, then=Value("prolific")),
                When(essay_count__gte=20, then=Value("regular")),
                When(essay_count__gte=5, then=Value("occasional")),
                default=Value("new"),
                output_field=CharField(),
            )
        )
        .order_by("-essay_count")
    )


def conditional_field_update():
    """
    Use Case/When inside update() for conditional bulk updates.

    Example: Set is_featured based on word count and recency for
    all published essays. This runs as a single SQL UPDATE.
    """
    from .models import Essay

    thirty_days_ago = timezone.now() - timedelta(days=30)

    Essay.objects.published().update(
        is_featured=Case(
            When(
                word_count__gte=3000,
                published_at__gte=thirty_days_ago,
                then=Value(True),
            ),
            default=Value(False),
        )
    )


# ---------------------------------------------------------------------------
# String and Transform Lookups
# ---------------------------------------------------------------------------

def essays_with_long_titles(min_length=100):
    """
    Filter by computed string length using Length database function.
    """
    from .models import Essay

    return Essay.objects.annotate(
        title_length=Length("title"),
    ).filter(title_length__gte=min_length)


def essays_title_starts_with(prefix):
    """
    Case-insensitive prefix matching.
    __istartswith is the case-insensitive version of __startswith.
    """
    from .models import Essay

    return Essay.objects.filter(
        title__istartswith=prefix,
        stage="published",
    )


def essays_matching_regex(pattern):
    """
    Regex filtering. Works on PostgreSQL, MySQL, and SQLite.
    __iregex is the case-insensitive variant.

    Example: essays_matching_regex(r'^(How|Why|What)\s')
    finds essays whose titles start with a question word.
    """
    from .models import Essay

    return Essay.objects.filter(
        title__iregex=pattern,
        stage="published",
    )


# ---------------------------------------------------------------------------
# Importing models (needed for the module-level import in models)
# ---------------------------------------------------------------------------
# Note: In real Django projects, these functions would import models at the
# module level. We use local imports here to keep the example self-contained
# and avoid circular import issues when models.py imports from this file.
