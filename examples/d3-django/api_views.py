"""
D3 + Django Integration: API Views
===================================

Django views that serve JSON data for D3.js visualizations. Each endpoint
demonstrates a different aggregation pattern and data shape commonly needed
by D3 charts.

Domain: Publishing API -- Essay, FieldNote, Tag models from the content app.

Key patterns:
    - TruncMonth for time-based grouping
    - Count + values() for grouped aggregation
    - Hierarchical (nested) data construction for treemaps
    - DjangoJSONEncoder for safe datetime serialization
    - cache_page for expensive aggregations
    - Proper Content-Type headers

Verify ORM aggregation against:
    refs/django-main/django/db/models/functions/datetime.py  (TruncMonth)
    refs/django-main/django/db/models/aggregates.py          (Count, Sum)
"""

import json
from collections import defaultdict
from datetime import timedelta

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from apps.content.models import Essay, FieldNote, Tag


# ---------------------------------------------------------------------------
# 1. Bar chart data: essays published per month
# ---------------------------------------------------------------------------

@require_GET
@cache_page(60 * 15)  # Cache 15 minutes; aggregation is expensive
def essays_per_month(request):
    """
    Returns monthly essay counts for bar/line charts.

    Query params:
        months (int): Number of months to look back. Default 12.

    Response shape (array of objects -- one per month):
        [
            {"month": "2025-01-01T00:00:00Z", "count": 5},
            {"month": "2025-02-01T00:00:00Z", "count": 3},
            ...
        ]

    D3 usage:
        x scale  -> d.month (temporal)
        y scale  -> d.count (linear)
    """
    months_back = min(int(request.GET.get("months", 12)), 36)
    cutoff = timezone.now() - timedelta(days=months_back * 30)

    data = (
        Essay.objects
        .filter(stage=Essay.Stage.PUBLISHED, published_at__gte=cutoff)
        .annotate(month=TruncMonth("published_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    # Convert queryset to list; DjangoJSONEncoder handles datetime objects.
    return JsonResponse(
        list(data),
        safe=False,
        encoder=DjangoJSONEncoder,
    )


# ---------------------------------------------------------------------------
# 2. Treemap data: essays grouped by content_type then tag
# ---------------------------------------------------------------------------

@require_GET
@cache_page(60 * 15)
def essays_by_category(request):
    """
    Returns hierarchical data for a D3 treemap or sunburst.

    Hierarchy: root -> content_type -> tag -> (leaf = essay count)

    Response shape:
        {
            "name": "essays",
            "children": [
                {
                    "name": "tutorial",
                    "children": [
                        {"name": "django", "value": 8},
                        {"name": "python", "value": 5}
                    ]
                },
                ...
            ]
        }

    D3 usage:
        d3.hierarchy(data).sum(d => d.value)
        then d3.treemap() or d3.partition()
    """
    published = Essay.objects.filter(stage=Essay.Stage.PUBLISHED)

    # Build a nested dict: content_type -> tag_name -> count
    tree = defaultdict(lambda: defaultdict(int))

    # Each essay can have multiple tags, so we iterate tag relationships.
    # Using values() on the M2M join to avoid loading full objects.
    rows = (
        published
        .values("content_type", "tags__name")
        .annotate(count=Count("id"))
        .order_by("content_type", "tags__name")
    )

    for row in rows:
        content_type = row["content_type"] or "uncategorized"
        tag_name = row["tags__name"] or "untagged"
        tree[content_type][tag_name] += row["count"]

    # Convert to D3 hierarchy format
    children = []
    for content_type, tags in sorted(tree.items()):
        tag_children = [
            {"name": tag, "value": count}
            for tag, count in sorted(tags.items())
        ]
        children.append({
            "name": content_type,
            "children": tag_children,
        })

    hierarchy = {
        "name": "essays",
        "children": children,
    }

    return JsonResponse(hierarchy)


# ---------------------------------------------------------------------------
# 3. Timeline data: publication events over time
# ---------------------------------------------------------------------------

@require_GET
@cache_page(60 * 15)
def publication_timeline(request):
    """
    Returns a time series of publication events for a timeline or line chart.
    Includes both Essay and FieldNote publications.

    Query params:
        days (int): Number of days to look back. Default 365.

    Response shape (array, sorted by date):
        [
            {
                "date": "2025-06-15T14:30:00Z",
                "title": "Building Django Models",
                "type": "essay",
                "content_type": "tutorial",
                "word_count": 2400,
                "tags": ["django", "python"]
            },
            {
                "date": "2025-06-16T09:00:00Z",
                "title": "Quick note on caching",
                "type": "field_note",
                "content_type": null,
                "word_count": null,
                "tags": ["django"]
            },
            ...
        ]

    D3 usage:
        x scale  -> d.date (temporal)
        y scale  -> d.word_count (linear, for essays) or stacked by type
        color    -> d.type or d.content_type
    """
    days_back = min(int(request.GET.get("days", 365)), 730)
    cutoff = timezone.now() - timedelta(days=days_back)

    # Essays with prefetched tags
    essays = (
        Essay.objects
        .filter(stage=Essay.Stage.PUBLISHED, published_at__gte=cutoff)
        .prefetch_related("tags")
        .order_by("published_at")
    )

    # FieldNotes with prefetched tags
    field_notes = (
        FieldNote.objects
        .filter(stage=FieldNote.Stage.PUBLISHED, published_at__gte=cutoff)
        .prefetch_related("tags")
        .order_by("published_at")
    )

    events = []

    for essay in essays:
        events.append({
            "date": essay.published_at,
            "title": essay.title,
            "type": "essay",
            "content_type": essay.content_type,
            "word_count": essay.word_count,
            "tags": list(essay.tags.values_list("name", flat=True)),
        })

    for note in field_notes:
        events.append({
            "date": note.published_at,
            "title": note.title,
            "type": "field_note",
            "content_type": None,
            "word_count": None,
            "tags": list(note.tags.values_list("name", flat=True)),
        })

    # Sort merged list by date
    events.sort(key=lambda e: e["date"])

    return JsonResponse(
        events,
        safe=False,
        encoder=DjangoJSONEncoder,
    )


# ---------------------------------------------------------------------------
# 4. Tag co-occurrence data: for network/chord diagrams
# ---------------------------------------------------------------------------

@require_GET
@cache_page(60 * 30)  # Heavier query, cache 30 minutes
def tag_cooccurrence(request):
    """
    Returns tag co-occurrence counts for a network graph or chord diagram.

    For each pair of tags that appear together on at least one published
    essay, returns the count of essays sharing both tags.

    Response shape:
        {
            "nodes": [
                {"id": "django", "count": 25},
                {"id": "python", "count": 18},
                ...
            ],
            "links": [
                {"source": "django", "target": "python", "value": 12},
                {"source": "django", "target": "celery", "value": 5},
                ...
            ]
        }

    D3 usage:
        d3.forceSimulation(nodes)
        d3.forceLink(links).id(d => d.id)
    """
    published_essays = Essay.objects.filter(stage=Essay.Stage.PUBLISHED)

    # Get all tags with their essay counts (only tags used by published essays)
    tags_with_counts = (
        Tag.objects
        .filter(essays__in=published_essays)
        .annotate(essay_count=Count("essays", filter=Q(essays__stage="published")))
        .filter(essay_count__gt=0)
        .values("name", "essay_count")
    )

    nodes = [
        {"id": t["name"], "count": t["essay_count"]}
        for t in tags_with_counts
    ]

    # Build co-occurrence links by finding essays that share tags.
    # For each published essay, get its tag set. Then count overlaps.
    cooccurrence = defaultdict(int)

    # Fetch essay->tags mapping in bulk to avoid N+1
    essay_tags = (
        published_essays
        .prefetch_related("tags")
        .values_list("id", "tags__name")
    )

    # Group tags by essay
    essay_tag_map = defaultdict(set)
    for essay_id, tag_name in essay_tags:
        if tag_name:
            essay_tag_map[essay_id].add(tag_name)

    # Count co-occurrences
    for tag_set in essay_tag_map.values():
        tag_list = sorted(tag_set)
        for i, tag_a in enumerate(tag_list):
            for tag_b in tag_list[i + 1:]:
                cooccurrence[(tag_a, tag_b)] += 1

    links = [
        {"source": pair[0], "target": pair[1], "value": count}
        for pair, count in sorted(cooccurrence.items())
        if count > 0
    ]

    return JsonResponse({"nodes": nodes, "links": links})


# ---------------------------------------------------------------------------
# URL configuration (add to your urls.py)
# ---------------------------------------------------------------------------

"""
from django.urls import path
from apps.content import api_views

urlpatterns = [
    path(
        "api/charts/essays-per-month/",
        api_views.essays_per_month,
        name="chart-essays-per-month",
    ),
    path(
        "api/charts/essays-by-category/",
        api_views.essays_by_category,
        name="chart-essays-by-category",
    ),
    path(
        "api/charts/publication-timeline/",
        api_views.publication_timeline,
        name="chart-publication-timeline",
    ),
    path(
        "api/charts/tag-cooccurrence/",
        api_views.tag_cooccurrence,
        name="chart-tag-cooccurrence",
    ),
]
"""
