# Django REST API Reference

This reference covers building REST APIs with Django REST Framework (DRF). For template-based views and URL patterns, see views.md.

## DRF ViewSets

ViewSets combine the logic for a set of related views into a single class. They map HTTP methods to actions automatically.

```python
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response


class EssayViewSet(viewsets.ModelViewSet):
    serializer_class = EssaySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['stage', 'draft']
    search_fields = ['title', 'slug', 'summary']
    ordering_fields = ['created_at', 'date']
    ordering = ['-date']
    lookup_field = 'slug'

    def get_queryset(self):
        return Essay.objects.published().select_related(
            'video_project'
        ).prefetch_related('linked_field_notes')

    def get_serializer_class(self):
        if self.action == 'list':
            return EssayListSerializer
        return EssayDetailSerializer

    @action(detail=True, methods=['post'])
    def publish(self, request, slug=None):
        essay = self.get_object()
        essay.publish(editor=request.user)
        return Response(EssayDetailSerializer(essay).data)

    @action(detail=False, methods=['get'])
    def in_progress(self, request):
        qs = self.get_queryset().filter(stage__in=['research', 'drafting', 'production'])
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = EssayListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = EssayListSerializer(qs, many=True)
        return Response(serializer.data)
```

**ViewSet action mapping:**
- `list()` - GET /essays/
- `create()` - POST /essays/
- `retrieve()` - GET /essays/{slug}/
- `update()` - PUT /essays/{slug}/
- `partial_update()` - PATCH /essays/{slug}/
- `destroy()` - DELETE /essays/{slug}/
- Custom `@action` - GET/POST /essays/{slug}/publish/ or /essays/in-progress/

**Alternatives:** `ReadOnlyModelViewSet` for read-only APIs. `GenericViewSet` with mixins for partial CRUD. Plain `APIView` for non-model endpoints.

## Serializer Patterns

Serializers are where API shape meets database shape. Keep them honest.

```python
from rest_framework import serializers


class EssayListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views."""
    source_count = serializers.IntegerField(read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)

    class Meta:
        model = Essay
        fields = [
            'id', 'title', 'slug', 'date', 'stage',
            'stage_display', 'source_count', 'draft',
            'tags', 'summary',
        ]


class EssayDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail/edit views."""
    sources = SourceReferenceSerializer(many=True, read_only=True)
    field_notes = FieldNoteSerializer(
        source='linked_field_notes', many=True, read_only=True
    )
    composition = serializers.JSONField(required=False)
    research_summary = serializers.SerializerMethodField()

    class Meta:
        model = Essay
        fields = [
            'id', 'title', 'slug', 'date', 'stage', 'draft',
            'summary', 'body', 'tags', 'thesis',
            'sources', 'field_notes',
            'composition', 'research_summary',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_research_summary(self, obj):
        return {
            'source_count': obj.source_count,
            'research_started': obj.research_started,
            'revision_count': obj.revision_count,
        }
```

**Serializer principles:**
- Separate serializers for list (lean) and detail (full) endpoints.
- Use `source` to reshape data, `write_only`/`read_only` to keep the contract clear.
- Validate API-specific rules at the serializer level; universal rules at the model level.

### Nested Write Serializers

When a create/update needs to accept nested data:

```python
class EssayCreateSerializer(serializers.ModelSerializer):
    sources = SourceReferenceSerializer(many=True, required=False)

    class Meta:
        model = Essay
        fields = ['title', 'slug', 'summary', 'body', 'stage', 'sources']

    def create(self, validated_data):
        sources_data = validated_data.pop('sources', [])
        essay = Essay.objects.create(**validated_data)
        for source_data in sources_data:
            SourceLink.objects.create(
                content_type='essay',
                content_slug=essay.slug,
                **source_data,
            )
        return essay
```

## Router Configuration

DRF routers generate URL patterns from ViewSets automatically.

```python
# apps/content/api_urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'content-api'

router = DefaultRouter()
router.register(r'essays', views.EssayViewSet, basename='essay')
router.register(r'field-notes', views.FieldNoteViewSet, basename='fieldnote')
router.register(r'sources', views.SourceViewSet, basename='source')

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
]
```

```python
# project_name/urls.py
urlpatterns = [
    path('api/v1/', include('apps.content.api_urls', namespace='content-api')),
]
```

**Router conventions:** `DefaultRouter` includes an API root view (`SimpleRouter` does not). Version in the URL prefix (`/api/v1/`). Use the router for ViewSets; plain `path()` for additional endpoints. Name every URL.

## Permissions

DRF permissions run before the view body executes.

```python
from rest_framework import permissions


class IsEditorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.has_perm('content.change_essay')


class CanPublishContent(permissions.BasePermission):
    message = 'You do not have permission to publish content.'

    def has_permission(self, request, view):
        return request.user.has_perm('content.can_publish')
```

**Apply permissions at the view level or globally:**

```python
class EssayViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsEditorOrReadOnly]

    def get_permissions(self):
        if self.action == 'publish':
            return [CanPublishContent()]
        return super().get_permissions()


# Global default
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
}
```

**Permission response behavior:**
- Unauthenticated: 401 Unauthorized. Authenticated but lacking permission: 403 Forbidden.
- Set `message` on custom permission classes to provide helpful error text.

## Throttling

Throttling prevents API abuse. Apply it globally or per-view.

```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'exports': '10/hour',
    },
}
```

For per-view throttling with custom scopes:

```python
from rest_framework.throttling import ScopedRateThrottle


class ContentExportView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'exports'
```

## Filtering and Search

Use `django-filter` for complex filtering. DRF's built-in `SearchFilter` and `OrderingFilter` handle common cases.

```python
# settings/base.py
REST_FRAMEWORK = {
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}
```

```python
import django_filters


class EssayFilter(django_filters.FilterSet):
    date_after = django_filters.DateFilter(
        field_name='date', lookup_expr='gte',
    )
    date_before = django_filters.DateFilter(
        field_name='date', lookup_expr='lte',
    )
    tag = django_filters.CharFilter(
        method='filter_by_tag',
    )

    class Meta:
        model = Essay
        fields = ['stage', 'draft']

    def filter_by_tag(self, queryset, name, value):
        return queryset.filter(tags__contains=[value])


class EssayViewSet(viewsets.ModelViewSet):
    filterset_class = EssayFilter
    search_fields = ['title', 'slug', 'summary', 'body']
    ordering_fields = ['created_at', 'date']
    ordering = ['-date']
```

## Pagination

Always paginate list endpoints. Unbounded querysets are the most common performance problem in Django APIs.

```python
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# Cursor-based pagination for large datasets
from rest_framework.pagination import CursorPagination


class EssayCursorPagination(CursorPagination):
    page_size = 25
    ordering = '-date'
    cursor_query_param = 'cursor'
```

**Pagination choices:** `PageNumberPagination` for most cases. `LimitOffsetPagination` when clients need page-size control. `CursorPagination` for large datasets or infinite scroll (consistent performance regardless of size).

## Serving Data for Charts

When D3 or other charting libraries consume your API, create dedicated endpoints that return pre-aggregated data. Do not make the frontend aggregate raw records.

```python
from django.db.models import Count, Sum, Avg, F, Q
from django.db.models.functions import TruncMonth
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def content_by_stage(request):
    """Bar chart data: content volume breakdown per stage."""
    data = (
        Essay.objects.values('stage')
        .annotate(
            total=Count('id'),
            with_sources=Count('id', filter=Q(source_count__gt=0)),
            avg_word_count=Avg(Length('body')),
        )
        .order_by('stage')
    )
    return Response(list(data))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def publications_over_time(request):
    """Line chart data: monthly publication count and word volume."""
    data = (
        Essay.objects
        .filter(date__isnull=False, stage='published')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(
            count=Count('id'),
            total_words=Sum(Length('body')),
        )
        .order_by('month')
    )
    return Response([
        {
            'month': row['month'].isoformat(),
            'count': row['count'],
            'total_words': row['total_words'] or 0,
        }
        for row in data
    ])
```

**On the template side**, pass data via `json_script` for initial render, or fetch from the API for dynamic updates. See d3-django.md for the full client-side pattern.

**Chart endpoint principles:**
- Aggregate in the database with Django ORM, not in Python or JavaScript.
- Return flat JSON arrays. D3 works best with arrays of objects.
- Use `TruncMonth`, `TruncWeek`, etc. for time-series data.
- Cast `Decimal` fields to `float` in the response - JSON does not have a decimal type.
- Add `?period=30d` or `?date_from=&date_to=` params for time-range filtering.

## Error Handling

Let DRF's exception handler format API errors consistently.

```python
from rest_framework.exceptions import ValidationError


class EssayViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        if Essay.objects.filter(slug=serializer.validated_data.get('slug')).exists():
            raise ValidationError({
                'slug': 'An essay with this slug already exists.'
            })
        serializer.save()
```

**Error handling principles:** Use DRF's built-in exceptions (`ValidationError`, `NotFound`, `PermissionDenied`) instead of raw `Response` objects with error codes. Log 500s with full context. Don't log 400s at ERROR level. Never expose tracebacks or SQL in production. Override `EXCEPTION_HANDLER` in settings to add request IDs or structured logging.

## API Documentation

Use drf-spectacular for automatic OpenAPI 3.0 schema generation:

```python
# pip install drf-spectacular
INSTALLED_APPS = ['drf_spectacular', ...]

REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'Content Publishing API',
    'DESCRIPTION': 'API for managing essays, field notes, and research sources.',
    'VERSION': '1.0.0',
}

# urls.py
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]
```

## Alternative: Django Ninja

Django Ninja is a lighter alternative to DRF using type hints instead of serializer classes. Consider it for async-first APIs, teams using Pydantic patterns, or straightforward CRUD without complex permission chains.

```python
from ninja import NinjaAPI, Schema

api = NinjaAPI(version='1.0.0')

class EssayOut(Schema):
    id: int
    title: str
    slug: str
    stage: str
    date: str | None

@api.get('/essays/', response=list[EssayOut])
def list_essays(request, stage: str = None):
    qs = Essay.objects.published()
    if stage:
        qs = qs.filter(stage=stage)
    return qs
```

DRF is the default recommendation (largest ecosystem, most community support). Ninja makes sense for greenfield async projects. Do not mix both in the same project.

## Anti-Patterns

- **Serializer logic in views.** Building response dicts manually in the view loses validation, documentation, and consistency.
- **N+1 queries in serializers.** A `SerializerMethodField` that hits the database per object executes N queries. Use `select_related`/`prefetch_related` in `get_queryset()`.
- **No pagination.** Every list endpoint needs pagination. An endpoint returning 50,000 objects will time out.
- **Ignoring `get_serializer_class()`.** Returning the full detail serializer for list views wastes bandwidth and queries.
- **Custom error formats.** DRF has a consistent error format. Don't override it without a specific reason.
