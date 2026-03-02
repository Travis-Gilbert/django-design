"""
DRF URL Configuration Patterns
===============================

Reference patterns for Django REST Framework router and URL configuration
using the content publishing domain.

Patterns covered:
    - DefaultRouter registration
    - SimpleRouter vs DefaultRouter
    - Nested router pattern (with drf-nested-routers)
    - Including router URLs in urlpatterns
    - Combining router URLs with standalone API views
    - API versioning via URL prefix

Verify against the actual DRF router implementation:
    refs/django-rest-framework-main/rest_framework/routers.py
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter, SimpleRouter

from .viewsets import EssayViewSet, FieldNoteViewSet, TagViewSet


# ---------------------------------------------------------------------------
# 1. DefaultRouter -- the standard approach
# ---------------------------------------------------------------------------

# DefaultRouter provides:
# - Automatic URL routing for ViewSets.
# - An API root view (browsable at the base URL).
# - .json format suffix support.
#
# SimpleRouter does the same but without the API root view. Use SimpleRouter
# when you do not need the root endpoint (e.g., in production APIs that
# have a separate docs page).

router = DefaultRouter()

# Register ViewSets. The first argument is the URL prefix, the second is
# the ViewSet, and `basename` is used to generate URL names.
#
# Generated URLs for EssayViewSet:
#   /api/essays/                -> essay-list
#   /api/essays/{pk}/           -> essay-detail
#   /api/essays/{pk}/publish/   -> essay-publish  (custom @action)
#   /api/essays/{pk}/unpublish/ -> essay-unpublish (custom @action)
#   /api/essays/published/      -> essay-public   (custom list @action)

router.register(r"essays", EssayViewSet, basename="essay")
router.register(r"tags", TagViewSet, basename="tag")
router.register(r"field-notes", FieldNoteViewSet, basename="fieldnote")


# ---------------------------------------------------------------------------
# 2. URL patterns
# ---------------------------------------------------------------------------

# The app_name enables URL namespacing for reverse():
#   reverse("content-api:essay-list")
#   reverse("content-api:essay-detail", kwargs={"pk": 1})

app_name = "content-api"

urlpatterns = [
    # Include all router-generated URLs under /api/.
    path("api/", include(router.urls)),

    # You can add standalone views alongside router URLs:
    # path("api/stats/", EssayStatsView.as_view(), name="essay-stats"),
]


# ---------------------------------------------------------------------------
# 3. Project-level URL configuration (typically in project/urls.py)
# ---------------------------------------------------------------------------

# In your project's root urls.py, include this app's URLs:
#
#   from django.contrib import admin
#   from django.urls import include, path
#
#   urlpatterns = [
#       path("admin/", admin.site.urls),
#       path("", include("apps.content.api.urls")),
#
#       # DRF browsable API login/logout (optional, for development):
#       path("api-auth/", include("rest_framework.urls")),
#   ]


# ---------------------------------------------------------------------------
# 4. API versioning via URL prefix
# ---------------------------------------------------------------------------

# If you version your API via URL (e.g., /api/v1/, /api/v2/), create
# separate routers or use a prefix:
#
#   v1_router = DefaultRouter()
#   v1_router.register(r"essays", EssayViewSetV1, basename="essay")
#
#   v2_router = DefaultRouter()
#   v2_router.register(r"essays", EssayViewSetV2, basename="essay")
#
#   urlpatterns = [
#       path("api/v1/", include((v1_router.urls, "v1"))),
#       path("api/v2/", include((v2_router.urls, "v2"))),
#   ]
#
# Then reverse with: reverse("v1:essay-list") or reverse("v2:essay-list").
#
# Alternative: Use DRF's built-in versioning classes in settings:
#   REST_FRAMEWORK = {
#       "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
#       "ALLOWED_VERSIONS": ["v1", "v2"],
#       "DEFAULT_VERSION": "v1",
#   }


# ---------------------------------------------------------------------------
# 5. Nested routers (using drf-nested-routers)
# ---------------------------------------------------------------------------

# For nested resources like /essays/{essay_pk}/revisions/, install
# drf-nested-routers: pip install drf-nested-routers
#
# Usage:
#
#   from rest_framework_nested import routers as nested_routers
#
#   # Parent router (same as above).
#   router = DefaultRouter()
#   router.register(r"essays", EssayViewSet, basename="essay")
#
#   # Nested router: revisions under essays.
#   essays_router = nested_routers.NestedDefaultRouter(
#       router, r"essays", lookup="essay"
#   )
#   essays_router.register(
#       r"revisions", EssayRevisionViewSet, basename="essay-revision"
#   )
#
#   # Generated URLs:
#   #   /api/essays/{essay_pk}/revisions/       -> essay-revision-list
#   #   /api/essays/{essay_pk}/revisions/{pk}/  -> essay-revision-detail
#
#   urlpatterns = [
#       path("api/", include(router.urls)),
#       path("api/", include(essays_router.urls)),
#   ]
#
#   # In EssayRevisionViewSet, access the parent PK:
#   #
#   #   def get_queryset(self):
#   #       return EssayRevision.objects.filter(
#   #           essay__pk=self.kwargs["essay_pk"]
#   #       )
#
# Note: drf-nested-routers is a third-party package, not built into DRF.
# Verify compatibility with your DRF version before adopting.


# ---------------------------------------------------------------------------
# 6. Lookup field customization
# ---------------------------------------------------------------------------

# By default, DRF uses `pk` for detail URLs: /essays/{pk}/.
# To use a slug instead: /essays/{slug}/
#
#   class EssayViewSet(viewsets.ModelViewSet):
#       lookup_field = "slug"
#       lookup_url_kwarg = "slug"  # Optional; defaults to lookup_field.
#
# Then the router generates:
#   /api/essays/{slug}/  instead of  /api/essays/{pk}/
#
# And reverse() works with:
#   reverse("essay-detail", kwargs={"slug": "my-essay-slug"})
