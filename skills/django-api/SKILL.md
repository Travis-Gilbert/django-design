---
name: django-api
description: Use when the user asks about REST APIs, DRF, Django REST Framework, serializers, viewsets, API endpoints, permissions, throttling, filtering, pagination, routers, Django Ninja, API versioning, external API integrations, or client class patterns.
version: 4.0.0
---

# Django API: REST Framework, Endpoints, and Integrations

This skill covers building and consuming APIs with Django: DRF viewsets and serializers, router configuration, permissions and throttling, filtering and pagination, external API integrations, and Django Ninja as an alternative.

## Reference Library

- **`references/api.md`** -- DRF ViewSets, serializer patterns (list vs detail), router config, permissions, throttling, filtering, pagination, Django Ninja alternatives
- **`references/integrations.md`** -- Client class pattern, authentication handling, retry with backoff, logging external calls, caching stable data, graceful degradation, testing mocked integrations

## Quick Guidance

### DRF Patterns

- Use `ModelViewSet` for standard CRUD. Use `ReadOnlyModelViewSet` when writes go through a different path.
- Split serializers: `ListSerializer` (minimal fields for lists) and `DetailSerializer` (full fields for detail views). Use `get_serializer_class()` to switch.
- Validation order: field-level `validate_<field>()` runs first, then `validate()` for cross-field logic.
- For nested writes, override `create()` and `update()` on the serializer. DRF does not handle nested writes automatically.
- Use `select_related`/`prefetch_related` in `get_queryset()` to prevent N+1 on serializer relations.

### Filtering and Search

- Use `django-filter` with `FilterSet` classes for structured filtering. Pair with DRF's `DjangoFilterBackend`.
- Use `SearchFilter` for free-text search across fields. Use `OrderingFilter` for client-controlled sorting.
- Always paginate list endpoints. `PageNumberPagination` or `CursorPagination` depending on dataset.

### Permissions and Throttling

- Set `DEFAULT_PERMISSION_CLASSES` in settings. Override per-view with `permission_classes`.
- Use `IsAuthenticated` as the baseline. Add `DjangoModelPermissions` or custom permissions for object-level access.
- Configure throttle rates for anonymous and authenticated users separately.

### External Integrations

- Wrap every external API behind a client class. Never call `requests.get()` directly from views.
- Add retry with exponential backoff for transient failures.
- Cache stable external data (user profiles, configuration) to reduce API calls.
- Log every external call with timing data for debugging.

## Anti-Patterns

- **Serializer-level database writes.** Keep `serializer.save()` simple. Complex multi-model writes belong in a service function.
- **N+1 in serializers.** A `SerializerMethodField` that queries the database means N+1. Use annotations or `prefetch_related`.
- **Overly broad permissions.** `AllowAny` on a viewset that should require auth. Set restrictive defaults, open selectively.
- **No pagination.** Returning unbounded querysets from list endpoints will eventually crash.
- **Hardcoded API keys in code.** Use environment variables. Always.

## Agents

| Agent | Focus |
|-------|-------|
| `drf-specialist` | Serializers, viewsets, permissions, filtering, pagination |
| `api-designer` | API architecture, endpoint design, versioning strategy |
| `django-api-reviewer` | Review existing API code for design quality and security |
