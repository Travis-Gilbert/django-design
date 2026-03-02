"""
DRF ViewSet Patterns
====================

Reference patterns for Django REST Framework viewsets using the content
publishing domain.

Patterns covered:
    - ModelViewSet with queryset optimization (select_related, prefetch_related)
    - Custom actions (@action decorator) for publish/unpublish
    - get_queryset() filtering by request.user
    - get_serializer_class() for action-based serializer switching
    - Permission classes per action via get_permissions()
    - Pagination class override
    - Filter backends (DjangoFilterBackend, SearchFilter, OrderingFilter)
    - Throttle scope
    - perform_create / perform_update hooks

All examples assume models, serializers, permissions, and filters are
defined in sibling modules. See the content-publishing-site example for
the full project structure.
"""

from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination, PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.content.models import Essay, FieldNote, Tag

from .filters import EssayFilterSet, FieldNoteFilterSet
from .permissions import CanPublish, IsAuthorOrReadOnly, IsEditorOrReadOnly
from .serializers import (
    EssayDetailSerializer,
    EssayListSerializer,
    EssayPublicSerializer,
    FieldNoteSerializer,
    TagSerializer,
)


# ---------------------------------------------------------------------------
# Custom pagination classes
# ---------------------------------------------------------------------------

class StandardPagination(PageNumberPagination):
    """
    Page-number pagination with a configurable page size.

    Key points:
    - page_size: default items per page.
    - page_size_query_param: allow the client to request a different size.
    - max_page_size: cap the client-requested size.
    """
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class FieldNoteCursorPagination(CursorPagination):
    """
    Cursor-based pagination for append-heavy models.

    Key points:
    - Cursor pagination provides consistent results when new items are
      added between page requests (no duplicates or skipped items).
    - Requires an ordering field that is unique and sequential.
    - Clients get opaque next/previous URLs instead of page numbers.
    """
    page_size = 50
    ordering = "-created_at"


# ---------------------------------------------------------------------------
# 1. EssayViewSet -- full-featured ModelViewSet
# ---------------------------------------------------------------------------

class EssayViewSet(viewsets.ModelViewSet):
    """
    Full CRUD plus custom actions for the Essay model.

    Key patterns demonstrated:
    - Queryset optimization with select_related and prefetch_related to
      avoid N+1 queries in serializer fields.
    - Separate serializer classes for list vs detail vs public access.
    - Per-action permission classes.
    - Filter backends: django-filter for structured filters, SearchFilter
      for full-text, OrderingFilter for sort control.
    - ScopedRateThrottle to limit write operations.
    - Custom @action endpoints for publish/unpublish workflows.
    """

    # -- Queryset --------------------------------------------------------

    queryset = Essay.objects.select_related("author").prefetch_related("tags")

    # -- Serializer selection --------------------------------------------

    serializer_class = EssayDetailSerializer

    def get_serializer_class(self):
        """
        Return a different serializer based on the action.

        Key points:
        - 'list' gets a lighter serializer (no body field).
        - 'public' custom action uses a serializer that hides unpublished
          content.
        - Everything else gets the full detail serializer.
        """
        if self.action == "list":
            return EssayListSerializer
        if self.action == "public":
            return EssayPublicSerializer
        return EssayDetailSerializer

    # -- Permissions per action ------------------------------------------

    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_permissions(self):
        """
        Override permissions for specific actions.

        Key points:
        - get_permissions() returns a list of permission *instances*.
        - Custom actions can have their own permission sets.
        - The publish action requires the CanPublish permission in
          addition to authentication.
        """
        if self.action == "publish":
            return [permissions.IsAuthenticated(), CanPublish()]
        if self.action == "destroy":
            return [permissions.IsAuthenticated(), IsAuthorOrReadOnly()]
        if self.action in ("update", "partial_update"):
            return [permissions.IsAuthenticated(), IsAuthorOrReadOnly()]
        return [permissions.IsAuthenticatedOrReadOnly()]

    # -- Filtering -------------------------------------------------------

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EssayFilterSet
    search_fields = ["title", "body", "summary"]
    ordering_fields = ["created_at", "published_at", "title"]
    ordering = ["-created_at"]

    # -- Pagination ------------------------------------------------------

    pagination_class = StandardPagination

    # -- Throttling ------------------------------------------------------

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "essays"
    # In settings.py:
    #   REST_FRAMEWORK = {
    #       "DEFAULT_THROTTLE_RATES": {
    #           "essays": "100/hour",
    #       }
    #   }

    # -- Queryset filtering by user --------------------------------------

    def get_queryset(self):
        """
        Filter the queryset based on the current user.

        Key points:
        - Authenticated users see their own drafts plus all published essays.
        - Anonymous users see only published essays.
        - Always call .select_related()/.prefetch_related() on the filtered
          queryset to maintain optimization.
        - Use self.request cautiously; it may be None during schema
          generation (e.g., with drf-spectacular).
        """
        qs = super().get_queryset()

        if self.request and self.request.user.is_authenticated:
            # Show the user's own essays (any stage) plus published by others.
            from django.db.models import Q
            qs = qs.filter(
                Q(author=self.request.user) | Q(stage="published")
            )
        else:
            qs = qs.filter(stage="published")

        return qs

    # -- Hooks -----------------------------------------------------------

    def perform_create(self, serializer):
        """
        Set the author from the request before saving.

        Key points:
        - perform_create/perform_update are hooks for injecting data
          that comes from the request context, not from the request body.
        - This keeps the serializer free of request awareness.
        """
        serializer.save(author=self.request.user)

    def perform_update(self, serializer):
        """
        Optionally record the last editor on update.
        """
        serializer.save(last_edited_by=self.request.user)

    # -- Custom actions --------------------------------------------------

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        """
        Transition an essay to 'published' stage.

        Key points:
        - @action(detail=True) creates an endpoint at /essays/{pk}/publish/.
        - detail=True means self.get_object() is available and
          has_object_permission is checked.
        - methods=["post"] restricts the HTTP methods.
        - url_path overrides the default URL segment (action method name).
        """
        essay = self.get_object()

        if essay.stage == "published":
            return Response(
                {"detail": "Essay is already published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not essay.body:
            return Response(
                {"detail": "Cannot publish an essay without a body."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        essay.stage = "published"
        essay.published_at = timezone.now()
        essay.save(update_fields=["stage", "published_at"])

        serializer = self.get_serializer(essay)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="unpublish")
    def unpublish(self, request, pk=None):
        """Revert a published essay back to drafting stage."""
        essay = self.get_object()

        if essay.stage != "published":
            return Response(
                {"detail": "Essay is not published."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        essay.stage = "drafting"
        essay.published_at = None
        essay.save(update_fields=["stage", "published_at"])

        serializer = self.get_serializer(essay)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="published")
    def public(self, request):
        """
        List only published essays for public consumption.

        Key points:
        - detail=False creates a list-level endpoint at /essays/published/.
        - Manually handle pagination for custom list actions.
        """
        qs = Essay.objects.filter(stage="published").select_related("author").prefetch_related("tags")
        qs = self.filter_queryset(qs)

        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# 2. TagViewSet -- simpler example with restricted actions
# ---------------------------------------------------------------------------

class TagViewSet(viewsets.ModelViewSet):
    """
    Tags are managed by editors only; everyone can read.

    Key points:
    - Restricting allowed methods by overriding http_method_names or
      by using mixin composition (e.g., mixins.ListModelMixin +
      mixins.RetrieveModelMixin + GenericViewSet for read-only).
    - Here we keep ModelViewSet but restrict via permissions.
    """

    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [IsEditorOrReadOnly]
    lookup_field = "slug"
    pagination_class = StandardPagination

    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "usage_count"]
    ordering = ["name"]


# ---------------------------------------------------------------------------
# 3. FieldNoteViewSet -- cursor pagination and owner-scoped queryset
# ---------------------------------------------------------------------------

class FieldNoteViewSet(viewsets.ModelViewSet):
    """
    Field notes are private to their author.

    Key points:
    - get_queryset() filters to the current user only.
    - Cursor pagination for chronologically ordered content.
    - perform_create sets the author from the request.
    """

    serializer_class = FieldNoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]
    pagination_class = FieldNoteCursorPagination

    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_class = FieldNoteFilterSet
    search_fields = ["title", "body"]

    def get_queryset(self):
        return FieldNote.objects.filter(
            author=self.request.user
        ).select_related("author").prefetch_related("tags")

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
