"""
DRF / django-filter FilterSet Patterns
=======================================

Reference patterns for django-filter integration with Django REST Framework
using the content publishing domain.

Patterns covered:
    - FilterSet with various field types (Char, Choice, Boolean, Date range)
    - Custom filter methods
    - CharFilter with lookup_expr
    - DateFromToRangeFilter for date range queries
    - NumberFilter for numeric comparisons
    - Ordering filter via OrderingFilter
    - Combining multiple filter types in one FilterSet

Verify against the actual django-filter source:
    refs/django-filter-main/django_filters/

Install: pip install django-filter
Settings: Add 'django_filters' to INSTALLED_APPS and configure:
    REST_FRAMEWORK = {
        'DEFAULT_FILTER_BACKENDS': [
            'django_filters.rest_framework.DjangoFilterBackend',
        ],
    }
"""

import django_filters
from django.db.models import Count, Q, QuerySet

from apps.content.models import Essay, FieldNote, Tag


# ---------------------------------------------------------------------------
# 1. EssayFilterSet -- comprehensive filtering
# ---------------------------------------------------------------------------

class EssayFilterSet(django_filters.FilterSet):
    """
    FilterSet for the Essay model demonstrating multiple filter types.

    Key points:
    - Each filter generates a query parameter (e.g., ?stage=published).
    - lookup_expr controls the SQL comparison (exact, icontains, gte, etc.).
    - method= delegates filtering to a custom Python method.
    - DateFromToRangeFilter generates two params: ?created_after= and
      ?created_before= (controlled by field_name + lookup suffixes).

    Example queries:
        GET /api/essays/?stage=published
        GET /api/essays/?title=climate
        GET /api/essays/?tags=python&tags=django
        GET /api/essays/?created_after=2025-01-01&created_before=2025-12-31
        GET /api/essays/?min_word_count=500
        GET /api/essays/?has_summary=true
        GET /api/essays/?author_username=jdoe
    """

    # -- Exact and choice filters ----------------------------------------

    stage = django_filters.ChoiceFilter(
        choices=[
            ("research", "Research"),
            ("drafting", "Drafting"),
            ("production", "Production"),
            ("published", "Published"),
        ],
        help_text="Filter by content stage.",
    )

    # -- Text search filters ---------------------------------------------

    title = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Case-insensitive substring match on the title.",
    )

    body_contains = django_filters.CharFilter(
        field_name="body",
        lookup_expr="icontains",
        help_text="Case-insensitive substring match on the body text.",
    )

    # -- Related field filters -------------------------------------------

    tags = django_filters.ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Tag.objects.all(),
        conjoined=False,  # OR logic: essay has ANY of the listed tags.
        help_text="Filter by tag names. Repeat for multiple: ?tags=python&tags=django",
    )

    author_username = django_filters.CharFilter(
        field_name="author__username",
        lookup_expr="exact",
        help_text="Filter by the author's username (exact match).",
    )

    # -- Date range filter -----------------------------------------------

    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
        help_text="Essays created on or after this date (YYYY-MM-DD).",
    )

    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="lte",
        help_text="Essays created on or before this date (YYYY-MM-DD).",
    )

    published_after = django_filters.DateFilter(
        field_name="published_at",
        lookup_expr="gte",
        help_text="Essays published on or after this date.",
    )

    published_before = django_filters.DateFilter(
        field_name="published_at",
        lookup_expr="lte",
        help_text="Essays published on or before this date.",
    )

    # -- Date range filter (alternative using DateFromToRangeFilter) ------

    created_range = django_filters.DateFromToRangeFilter(
        field_name="created_at",
        help_text=(
            "Date range for created_at. Use ?created_range_after=2025-01-01"
            "&created_range_before=2025-12-31"
        ),
    )

    # -- Boolean filter --------------------------------------------------

    has_summary = django_filters.BooleanFilter(
        method="filter_has_summary",
        help_text="Filter essays that have (true) or lack (false) a summary.",
    )

    # -- Numeric filter --------------------------------------------------

    min_word_count = django_filters.NumberFilter(
        method="filter_min_word_count",
        help_text="Minimum word count (server-estimated from body length).",
    )

    # -- Custom filter methods -------------------------------------------

    def filter_has_summary(self, queryset: QuerySet, name: str, value: bool) -> QuerySet:
        """
        Custom filter method for boolean-like conditions.

        Key points:
        - The `name` parameter is the filter field name ("has_summary").
        - The `value` parameter is the parsed boolean.
        - Return the filtered queryset.
        - Exclude empty strings as well as NULL for text fields.
        """
        if value:
            return queryset.exclude(summary__isnull=True).exclude(summary="")
        return queryset.filter(Q(summary__isnull=True) | Q(summary=""))

    def filter_min_word_count(self, queryset: QuerySet, name: str, value: int) -> QuerySet:
        """
        Custom filter using annotation.

        Key points:
        - For computed values not stored in the database, annotate the
          queryset and filter on the annotation.
        - This uses a rough heuristic (body length / 5) because word count
          is not stored. For exact filtering, consider a denormalized field.
        """
        # Rough estimate: average word length ~5 chars.
        min_chars = value * 5
        return queryset.exclude(body__isnull=True).exclude(body="").extra(
            where=["LENGTH(body) >= %s"],
            params=[min_chars],
        )

    class Meta:
        model = Essay
        fields = []  # All fields defined explicitly above.


# ---------------------------------------------------------------------------
# 2. FieldNoteFilterSet -- simpler example
# ---------------------------------------------------------------------------

class FieldNoteFilterSet(django_filters.FilterSet):
    """
    FilterSet for FieldNote with basic filters.

    Key points:
    - For simple exact-match filters, list field names in Meta.fields
      and django-filter generates them automatically.
    - Combine with explicit filters for more control.
    """

    title = django_filters.CharFilter(
        lookup_expr="icontains",
        help_text="Substring match on title.",
    )

    tags = django_filters.ModelMultipleChoiceFilter(
        field_name="tags__name",
        to_field_name="name",
        queryset=Tag.objects.all(),
    )

    created_after = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="gte",
    )

    created_before = django_filters.DateFilter(
        field_name="created_at",
        lookup_expr="lte",
    )

    class Meta:
        model = FieldNote
        fields = []


# ---------------------------------------------------------------------------
# 3. TagFilterSet -- ordering by usage count
# ---------------------------------------------------------------------------

class TagFilterSet(django_filters.FilterSet):
    """
    FilterSet for Tag with annotation-based ordering.

    Key points:
    - OrderingFilter from django-filter (different from DRF's OrderingFilter).
    - Annotate queryset for computed ordering fields.
    """

    name = django_filters.CharFilter(
        lookup_expr="icontains",
    )

    ordering = django_filters.OrderingFilter(
        fields=(
            ("name", "name"),
            ("usage_count", "usage_count"),
        ),
        help_text="Order by: name, -name, usage_count, -usage_count",
    )

    class Meta:
        model = Tag
        fields = []
