"""
HTMX Pattern: URL Configuration
================================

Demonstrates URL patterns for HTMX endpoints in a Django content
publishing site. Shows two organizational strategies:

1. HTMX endpoints live alongside their full-page counterparts in the
   app's own urlpatterns (simpler, recommended for most projects).

2. HTMX-only endpoints live in a separate namespace for partials and
   fragments that have no full-page equivalent (modals, inline forms,
   empty responses).

Naming conventions:
- Full-page views: "essays:list", "essays:detail"
- HTMX partials in same app: "essays:search", "essays:feed"
- HTMX-only endpoints: "htmx:essay_notes", "htmx:tag_create_modal"

Domain: Publishing API with Essay, Tag, FieldNote models.
"""

from django.urls import include, path


# ---------------------------------------------------------------------------
# Strategy 1: HTMX endpoints alongside full-page views (recommended)
# ---------------------------------------------------------------------------

# --- apps/content/urls/essays.py ---

from apps.content.views import htmx_views, page_views

app_name = "essays"

urlpatterns = [
    # Full-page views (also handle HTMX via request.htmx check)
    path("", page_views.essay_list, name="list"),
    path("feed/", page_views.essay_feed, name="feed"),
    path("<slug:slug>/", page_views.essay_detail, name="detail"),
    path("<slug:slug>/edit/", page_views.essay_edit, name="edit"),

    # HTMX endpoints that live in the same namespace.
    # These return partials only and are not meant for direct browser access.
    # Naming them descriptively avoids confusion with the full-page views.
    path("search/", htmx_views.essay_search, name="search"),
    path("quick-create/", htmx_views.essay_quick_create, name="quick_create"),
    path("bulk-action/", htmx_views.essay_bulk_action, name="bulk_action"),
    path(
        "<slug:slug>/publish/",
        htmx_views.essay_publish,
        name="publish",
    ),
    path(
        "<slug:slug>/advance/",
        htmx_views.essay_stage_advance,
        name="stage_advance",
    ),
    path(
        "<slug:slug>/save/",
        htmx_views.essay_save,
        name="save",
    ),
    path(
        "export/<str:task_id>/status/",
        htmx_views.essay_export_status,
        name="export_status",
    ),
]


# --- apps/content/urls/notes.py ---

from apps.content.views import htmx_views as note_htmx_views

app_name = "notes"

note_urlpatterns = [
    # Full-page views
    path("", page_views.field_note_list, name="list"),

    # HTMX endpoints: edit-in-place, delete, row reload
    path("<int:pk>/edit/", note_htmx_views.field_note_edit, name="edit"),
    path("<int:pk>/delete/", note_htmx_views.field_note_delete, name="delete"),
    path("<int:pk>/row/", note_htmx_views.field_note_row, name="row"),
]


# ---------------------------------------------------------------------------
# Strategy 2: Separate HTMX namespace for fragment-only endpoints
# ---------------------------------------------------------------------------

# Some HTMX endpoints do not correspond to any full-page view. They serve
# modals, tab content, empty responses, and other fragments. Grouping
# them in a dedicated namespace keeps app urlconfs clean and makes it
# obvious that these endpoints return partials only.
#
# Convention: prefix view names with the content area they serve.

from apps.content.views import htmx_views as content_htmx_views

app_name_htmx = "htmx"

htmx_urlpatterns = [
    # Essay tab content (used by tab navigation on essay detail page)
    path(
        "essays/<slug:slug>/notes/",
        content_htmx_views.essay_notes_tab,
        name="essay_notes",
    ),
    path(
        "essays/<slug:slug>/history/",
        content_htmx_views.essay_history_tab,
        name="essay_history",
    ),

    # Quick create form (loaded into #quick-create container)
    path(
        "essays/quick-create-form/",
        content_htmx_views.essay_quick_create_form,
        name="essay_quick_create_form",
    ),

    # Tag modal
    path(
        "tags/create-modal/",
        content_htmx_views.tag_create_modal,
        name="tag_create_modal",
    ),

    # Utility: return empty response (used to clear containers)
    path(
        "empty/",
        content_htmx_views.empty_response,
        name="empty",
    ),
]


# ---------------------------------------------------------------------------
# Root URL configuration
# ---------------------------------------------------------------------------

# --- config/urls.py ---

root_urlpatterns = [
    path("essays/", include(("apps.content.urls.essays", "essays"))),
    path("notes/", include(("apps.content.urls.notes", "notes"))),
    path("tags/", include(("apps.content.urls.tags", "tags"))),

    # HTMX-only endpoints under /_htmx/ prefix.
    # The underscore prefix signals that these are internal endpoints
    # not meant for direct browser navigation. Some teams use /partials/
    # or /fragments/ instead.
    path("_htmx/", include((htmx_urlpatterns, "htmx"))),
]


# ---------------------------------------------------------------------------
# Notes on URL organization
# ---------------------------------------------------------------------------

# Approach 1 (mixed) is simpler and works well when most HTMX endpoints
# are variations of existing views (search, save, delete). The view
# checks request.htmx to decide whether to return a full page or partial.
#
# Approach 2 (separate namespace) is useful for:
#   - Endpoints that have no full-page equivalent (modals, tab content)
#   - Teams that want a clear separation between page and fragment URLs
#   - Projects where you want to apply different middleware or rate
#     limiting to HTMX endpoints
#
# Both approaches can coexist in the same project. Use whichever fits
# each situation.
#
# Security note: HTMX endpoints should use the same authentication and
# permission checks as their full-page equivalents. The django-htmx
# middleware only adds the request.htmx attribute; it does not bypass
# Django's auth system. Use @login_required, @permission_required, or
# DRF permissions as you normally would.


# ---------------------------------------------------------------------------
# Utility view for empty responses
# ---------------------------------------------------------------------------

# This simple view returns an empty response. It is used when a cancel
# button needs to clear a container (like the quick-create form).

from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def empty_response(request) -> HttpResponse:
    """Return an empty 200 response. Used to clear HTMX target containers."""
    return HttpResponse("")
