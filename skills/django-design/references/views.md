# Django Views and URL Patterns Reference

## Function-Based vs Class-Based Views

This is not a religious debate. Both are tools with different strengths.

**Use function-based views when:**
- The logic is linear and specific to one endpoint
- You're handling a form submission with custom validation flow
- The view does something unusual that doesn't fit a generic pattern
- You want maximum readability for someone new to the codebase

**Use class-based views when:**
- You're building standard CRUD operations
- You need to share behavior across multiple views (mixins)
- Django's generic views (ListView, DetailView, CreateView) match your use case
- You're building a REST API with DRF ViewSets

**Use DRF ViewSets when:**
- You're building a REST API that follows standard patterns
- You want automatic routing, serialization, and content negotiation
- The API maps cleanly to models

```python
# Function-based: clear, linear, easy to follow
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


@require_http_methods(["GET"])
def property_compliance_summary(request, property_id):
    """Return compliance summary for a single property."""
    property = get_object_or_404(
        Property.objects.with_compliance_stats(),
        pk=property_id,
    )
    
    if not request.user.has_perm('properties.view_property'):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    return JsonResponse({
        'property_id': str(property.id),
        'address': property.address,
        'status': property.status,
        'days_owned': property.days_owned.days,
        'documents_submitted': property.document_count,
        'is_overdue': property.is_overdue,
    })


# Class-based: leverages Django's generic patterns
from django.views.generic import ListView


class PropertyListView(LoginRequiredMixin, ListView):
    model = Property
    template_name = 'properties/list.html'
    context_object_name = 'properties'
    paginate_by = 25
    
    def get_queryset(self):
        qs = Property.objects.active().select_related('buyer', 'assigned_to')
        
        program = self.request.GET.get('program')
        if program:
            qs = qs.for_program(program)
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['programs'] = Property.objects.values_list(
            'program', flat=True
        ).distinct()
        return context


# DRF ViewSet: full REST API with minimal code
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response


class PropertyViewSet(viewsets.ModelViewSet):
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ['program', 'status']
    search_fields = ['address', 'parcel_id']
    ordering_fields = ['created_at', 'purchase_date']
    ordering = ['-created_at']
    
    def get_queryset(self):
        return Property.objects.active().select_related(
            'buyer', 'assigned_to'
        ).prefetch_related('documents')
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Custom action for compliance approval."""
        property = self.get_object()
        property.approve(reviewer=request.user)
        return Response(PropertySerializer(property).data)
```

## DRF Serializer Patterns

Serializers are where API shape meets database shape. Keep them honest.

```python
from rest_framework import serializers


class PropertyListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views. Only include what the
    list page needs to render each row."""
    buyer_name = serializers.CharField(source='buyer.full_name', read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Property
        fields = [
            'id', 'address', 'parcel_id', 'program',
            'status', 'buyer_name', 'is_overdue',
        ]


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail/edit views."""
    buyer = BuyerSerializer(read_only=True)
    buyer_id = serializers.PrimaryKeyRelatedField(
        queryset=Buyer.objects.all(),
        source='buyer',
        write_only=True,
    )
    documents = DocumentSerializer(many=True, read_only=True)
    compliance_summary = serializers.SerializerMethodField()
    
    class Meta:
        model = Property
        fields = [
            'id', 'address', 'parcel_id', 'program', 'status',
            'purchase_date', 'purchase_price',
            'buyer', 'buyer_id',
            'documents', 'compliance_summary',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_compliance_summary(self, obj):
        return {
            'total_required': obj.required_document_count,
            'total_submitted': obj.documents.count(),
            'days_remaining': obj.days_until_deadline,
        }
```

**Serializer principles:**
- Use separate serializers for list and detail endpoints. List serializers should be lean.
- Use `source` to reshape data without changing model structure.
- Keep computed fields in `SerializerMethodField` or model properties, not in the view.
- Use `write_only=True` / `read_only=True` to keep the API contract clear.
- Validate at the serializer level for API-specific rules, at the model level for universal rules.

## URL Patterns

```python
# project_name/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.properties.urls', namespace='properties-api')),
    path('', include('apps.portal.urls', namespace='portal')),
]


# apps/properties/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'properties'

router = DefaultRouter()
router.register(r'properties', views.PropertyViewSet, basename='property')

urlpatterns = [
    path('', include(router.urls)),
    # Non-CRUD endpoints that don't fit the ViewSet pattern
    path('dashboard/stats/', views.dashboard_stats, name='dashboard-stats'),
    path('export/', views.export_properties, name='export'),
]
```

**URL conventions:**
- Always set `app_name` for URL namespacing. This prevents collisions.
- Use `include()` to keep each app's URLs in its own file.
- API versioning in the URL prefix (`/api/v1/`) is simple and works. Don't overthink it.
- Use DRF's router for ViewSets. Define additional endpoints as plain `path()` entries.
- Name every URL. Templates use `{% url 'properties:property-list' %}`, code uses `reverse('properties:property-list')`.

## Middleware

Custom middleware should be rare and focused. If it's doing heavy lifting, it probably belongs in a view decorator or a mixin instead.

```python
# apps/core/middleware.py
import time
import logging

logger = logging.getLogger('django.request')


class RequestTimingMiddleware:
    """Log request duration for performance monitoring."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start
        
        if duration > 1.0:  # log slow requests
            logger.warning(
                'Slow request: %s %s took %.2fs',
                request.method, request.path, duration,
            )
        
        response['X-Request-Duration'] = f'{duration:.3f}'
        return response


class CurrentUserMiddleware:
    """Make the current user available to model methods
    without passing request around everywhere.
    
    Use sparingly. This uses thread-local storage which
    doesn't work with async views.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        from apps.core.context import set_current_user
        set_current_user(request.user)
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)
```

## Pagination

Always paginate list endpoints. Unbounded querysets are the most common performance problem in Django APIs.

```python
# For DRF, set defaults in settings
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
}

# For cursor-based pagination (better for large datasets)
from rest_framework.pagination import CursorPagination


class PropertyCursorPagination(CursorPagination):
    page_size = 25
    ordering = '-created_at'
    cursor_query_param = 'cursor'


# For template-based views, use Django's built-in Paginator
from django.core.paginator import Paginator


def property_list(request):
    properties = Property.objects.active().select_related('buyer')
    paginator = Paginator(properties, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'properties/list.html', {'page': page})
```

**Pagination choices:**
- `PageNumberPagination`: Simple, works for most cases. Users can jump to any page.
- `LimitOffsetPagination`: Good for APIs where clients want control over page size.
- `CursorPagination`: Best for large datasets, real-time data, or infinite scroll. No page-jumping, but consistent performance.

## File Upload Handling

```python
from django.core.validators import FileExtensionValidator


class ComplianceDocument(TimeStampedModel):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=50, choices=DocumentType.choices)
    file = models.FileField(
        upload_to='compliance/%Y/%m/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png']),
        ],
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    file_size = models.PositiveIntegerField(editable=False)
    
    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


# In the view or serializer, validate file size
def validate_file(file):
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size > max_size:
        raise ValidationError(f'File size must be under 10MB. Got {file.size / 1024 / 1024:.1f}MB.')
```

For production file storage, use `django-storages` with S3 or equivalent:

```python
# settings/production.py
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
}
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')
AWS_DEFAULT_ACL = 'private'  # never default to public
```

## Error Handling

```python
# For API views, use DRF's exception handling
from rest_framework.exceptions import ValidationError, NotFound


class PropertyViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        buyer = serializer.validated_data.get('buyer')
        if buyer.has_outstanding_violations:
            raise ValidationError({
                'buyer': 'This buyer has outstanding violations and cannot purchase properties.'
            })
        serializer.save()


# For template views, use Django's error handling
from django.http import Http404, HttpResponseBadRequest


def property_detail(request, property_id):
    try:
        property = Property.objects.select_related('buyer').get(pk=property_id)
    except Property.DoesNotExist:
        raise Http404('Property not found')
    
    return render(request, 'properties/detail.html', {'property': property})


# Custom error views
# urls.py
handler404 = 'apps.core.views.custom_404'
handler500 = 'apps.core.views.custom_500'
```

**Error handling principles:**
- Let DRF's exception handler format API errors consistently. Don't return custom JSON error shapes.
- Use `get_object_or_404()` as a shortcut when you just need to fetch or 404.
- Log server errors (500s) with full context. Don't log client errors (400s) at ERROR level since those are expected.
- Never expose internal error details (tracebacks, SQL queries) in production responses.
