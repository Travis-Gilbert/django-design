---
description: Scaffold DRF API endpoints for a Django model - ViewSet, serializers, URLs, permissions, and tests
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
argument-hint: (interactive - no arguments needed)
---

# Django API Scaffolding

Generate a complete DRF API layer for an existing Django model: ViewSet, serializers (list + detail), URL router registration, permission classes, and tests.

## Phase 1: Discover the Model

Read the project to understand what exists.

### Step 1: Find the model

```bash
# Find all models.py files
find . -name "models.py" -not -path "*/migrations/*" -not -path "*/.venv/*" | head -20
```

Read each `models.py` to build a model inventory.

### Step 2: Check for existing API infrastructure

```bash
# Check if DRF is installed
grep -r "rest_framework" */settings*.py settings/*.py 2>/dev/null
# Find existing serializers and API views
find . -name "serializers.py" -o -name "api_views.py" -o -name "api.py" | head -20
# Find existing URL router setup
grep -rn "router" */urls.py urls.py 2>/dev/null
```

### Step 3: Gather requirements

Ask the user two questions:

**Question 1: Which model?**

Present the discovered models as options. Include "Other" for models not yet found.

**Question 2: What API style?**

Options:
- **Full CRUD** - All operations: list, create, retrieve, update, partial_update, destroy
- **Read-only** - List and retrieve only (for reference data, dashboards)
- **Read + Create** - List, retrieve, and create (for intake forms, submissions)
- **Custom** - Let me specify which actions

## Phase 2: Design the Endpoint

### Step 1: Analyze the model

Read the selected model's full definition. Identify:

- All fields and their types
- Relationships (ForeignKey, ManyToMany, OneToOne)
- Any custom managers or querysets
- Properties and methods that might be useful as serializer fields
- Existing indexes and constraints

### Step 2: Design the serializer fields

Determine field groupings:

**List serializer** (minimal fields for table/card display):
- Primary key
- Display name / title field
- Status field (if any)
- Key summary fields (2-3 max)
- Related object names (not full nested objects)

**Detail serializer** (full representation):
- All safe fields (exclude passwords, tokens, internal-only fields)
- Nested related objects (with separate nested serializers)
- Computed fields from model properties
- Hyperlinked related endpoints

### Step 3: Confirm with user

Present the proposed endpoint design:

```
Endpoint: /api/v1/{app_name}/{model_name_plural}/
Actions: [list, create, retrieve, update, partial_update, destroy]

List serializer fields: [id, title, slug, stage, word_count, date]
Detail serializer fields: [id, title, slug, body, thesis, summary, stage, word_count, date, created_by, draft, ...]

Permissions: IsAuthenticated (default)
Pagination: PageNumberPagination (page_size=25)
Filtering: stage, draft, date range
Search: title, slug, body
Ordering: date, stage, created_at
```

Ask: "Does this endpoint design look right? Any fields to add/remove?"

## Phase 3: Generate the Code

Generate all files in order: serializers, views, URLs, tests.

### Step 1: Serializers

Create or update `{app}/serializers.py`:

```python
from rest_framework import serializers
from .models import {Model}


class {Model}ListSerializer(serializers.ModelSerializer):
    """Minimal representation for list endpoints."""

    class Meta:
        model = {Model}
        fields = [
            'id',
            # list fields...
        ]
        read_only_fields = ['id']


class {Model}DetailSerializer(serializers.ModelSerializer):
    """Full representation for detail endpoints."""

    # Nested serializers for related objects
    # created_by = UserSummarySerializer(read_only=True)

    class Meta:
        model = {Model}
        fields = [
            'id',
            # all fields...
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class {Model}CreateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for create/update operations."""

    class Meta:
        model = {Model}
        fields = [
            # writable fields...
        ]

    def validate(self, attrs):
        """Cross-field validation."""
        # Add business rule validation here
        return attrs
```

### Step 2: ViewSet

Create or update `{app}/api_views.py`:

```python
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import {Model}
from .serializers import (
    {Model}ListSerializer,
    {Model}DetailSerializer,
    {Model}CreateUpdateSerializer,
)


class {Model}ViewSet(viewsets.ModelViewSet):
    """
    API endpoint for {Model} resources.

    list: Return paginated list of {model_plural}.
    create: Create a new {model}.
    retrieve: Return a single {model} with full details.
    update: Update all fields of a {model}.
    partial_update: Update specific fields of a {model}.
    destroy: Delete a {model}.
    """
    queryset = {Model}.objects.select_related(
        # related fields used by serializers
    ).prefetch_related(
        # many-to-many or reverse FK fields
    )
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        # 'stage': ['exact'],
        # 'draft': ['exact'],
        # 'date': ['gte', 'lte'],
    }
    search_fields = [
        # 'title', 'slug', 'body',
    ]
    ordering_fields = [
        # 'date', 'stage', 'created_at',
    ]
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'list':
            return {Model}ListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return {Model}CreateUpdateSerializer
        return {Model}DetailSerializer
```

### Step 3: URL Configuration

Update or create `{app}/urls.py` (API section):

```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'{model_plural}', api_views.{Model}ViewSet)

app_name = '{app}'

urlpatterns = [
    # Template-based views...
    path('api/v1/', include(router.urls)),
]
```

If the project uses a central API router, register there instead:

```python
# project_name/urls.py
from apps.{app}.api_views import {Model}ViewSet

router = DefaultRouter()
router.register(r'{model_plural}', {Model}ViewSet)

urlpatterns = [
    path('api/v1/', include(router.urls)),
]
```

### Step 4: Tests

Create or update `{app}/tests/test_api.py`:

```python
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.{app}.models import {Model}
# from apps.{app}.factories import {Model}Factory  # if using factory_boy


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='testuser', password='testpass123'
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class Test{Model}API:
    """Tests for the {Model} API endpoints."""

    def test_list_requires_auth(self, api_client):
        url = reverse('{app}:{model}-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_returns_paginated_results(self, authenticated_client):
        # Create test data
        # {Model}Factory.create_batch(5)
        url = reverse('{app}:{model}-list')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'count' in response.data

    def test_retrieve_returns_detail_fields(self, authenticated_client):
        # instance = {Model}Factory.create()
        # url = reverse('{app}:{model}-detail', args=[instance.pk])
        # response = authenticated_client.get(url)
        # assert response.status_code == status.HTTP_200_OK
        # Assert detail-specific fields are present
        pass

    def test_create_with_valid_data(self, authenticated_client):
        url = reverse('{app}:{model}-list')
        data = {
            # valid creation data
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED

    def test_create_with_invalid_data(self, authenticated_client):
        url = reverse('{app}:{model}-list')
        data = {}  # empty/invalid data
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_by_status(self, authenticated_client):
        # Create instances with different statuses
        url = reverse('{app}:{model}-list')
        response = authenticated_client.get(url, {'status': 'active'})
        assert response.status_code == status.HTTP_200_OK
        # Assert all results have the filtered status

    def test_search(self, authenticated_client):
        url = reverse('{app}:{model}-list')
        response = authenticated_client.get(url, {'search': 'test query'})
        assert response.status_code == status.HTTP_200_OK
```

## Phase 4: Review and Validate

### Step 1: Verify queryset optimization

Read the serializers and confirm that every nested serializer or related field has a corresponding `select_related` or `prefetch_related` in the ViewSet's queryset.

### Step 2: Check URL registration

Verify the router is included in the project's URL configuration and the API is reachable.

### Step 3: Summary

Present a summary of what was generated:

```
Generated API for {Model}:
  - Serializers: {Model}ListSerializer, {Model}DetailSerializer, {Model}CreateUpdateSerializer
  - ViewSet: {Model}ViewSet with {actions}
  - URL: /api/v1/{model_plural}/
  - Permissions: IsAuthenticated
  - Filtering: {filter_fields}
  - Search: {search_fields}
  - Tests: {test_count} test cases

Next steps:
  1. Run migrations if any model changes were needed
  2. Install django-filter if not already installed: pip install django-filter
  3. Run tests: pytest {app}/tests/test_api.py -v
  4. Check the browsable API at /api/v1/{model_plural}/ (development only)
```
