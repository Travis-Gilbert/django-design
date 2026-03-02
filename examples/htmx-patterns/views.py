"""
HTMX Pattern: Views
====================

Demonstrates HTMX-aware Django views for a content publishing site.
Covers full-page vs partial rendering, django-htmx middleware usage,
client-side redirects and refreshes, HX-Trigger events, infinite scroll
pagination, search-as-you-type, form submission with fragment updates,
and delete with confirmation.

Requires:
    - django-htmx (HtmxMiddleware in MIDDLEWARE)
    - django-template-partials (for #partial-name rendering)

Domain: Publishing API with Essay, Tag, FieldNote models.
"""

from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from django_htmx.http import (
    HttpResponseClientRedirect,
    HttpResponseClientRefresh,
    HttpResponseLocation,
    HttpResponseStopPolling,
    push_url,
    retarget,
    reswap,
    trigger_client_event,
)
from django_htmx.middleware import HtmxDetails

from apps.content.forms import EssayForm, FieldNoteForm
from apps.content.models import Essay, FieldNote, Tag


# ---------------------------------------------------------------------------
# Typed request (recommended by django-stubs)
# ---------------------------------------------------------------------------

class HtmxHttpRequest(HttpRequest):
    htmx: HtmxDetails


# ---------------------------------------------------------------------------
# Pattern 1: Full page vs partial based on HX-Request header
# ---------------------------------------------------------------------------

@require_GET
def essay_list(request: HtmxHttpRequest) -> HttpResponse:
    """
    Return the full page on a normal request, or just the essay list
    fragment on an HTMX request.

    Uses django-template-partials: the template defines a named partial
    with {% partialdef essay-list inline %}...{% endpartialdef %} and
    we render only that partial by appending #essay-list to the
    template name.
    """
    essays = Essay.objects.published().select_related("author")
    page = Paginator(essays, 20).get_page(request.GET.get("page", "1"))

    template_name = "content/essay_list.html"
    if request.htmx and not request.htmx.boosted:
        template_name += "#essay-list"

    return render(request, template_name, {"page": page})


@require_GET
def essay_detail(request: HtmxHttpRequest, slug: str) -> HttpResponse:
    """
    Full page on normal request. On HTMX request, return only the
    content section. Useful for tab navigation where the shell stays
    and only the content area swaps.
    """
    essay = get_object_or_404(
        Essay.objects.select_related("author").prefetch_related("tags"),
        slug=slug,
        stage=Essay.Stage.PUBLISHED,
    )

    template_name = "content/essay_detail.html"
    if request.htmx:
        template_name += "#essay-content"

    return render(request, template_name, {"essay": essay})


# ---------------------------------------------------------------------------
# Pattern 2: Client-side redirect and refresh
# ---------------------------------------------------------------------------

@require_POST
def essay_publish(request: HtmxHttpRequest, slug: str) -> HttpResponse:
    """
    Publish an essay, then redirect the client to its public page.

    HttpResponseClientRedirect sets the HX-Redirect header, which tells
    HTMX to do a full-page navigation to the target URL. This is
    appropriate after state-changing actions where you want the browser
    URL to update and the full page to reload.
    """
    essay = get_object_or_404(Essay, slug=slug, author=request.user)
    essay.publish()

    if request.htmx:
        return HttpResponseClientRedirect(essay.get_absolute_url())

    return redirect(essay.get_absolute_url())


@require_POST
def essay_stage_advance(request: HtmxHttpRequest, slug: str) -> HttpResponse:
    """
    Advance an essay to its next pipeline stage, then refresh the
    current page to reflect the new state.

    HttpResponseClientRefresh sets the HX-Refresh header, which tells
    HTMX to reload the entire current page. Useful when many parts of
    the page depend on the changed state.
    """
    essay = get_object_or_404(Essay, slug=slug, author=request.user)
    essay.next_stage()

    if request.htmx:
        return HttpResponseClientRefresh()

    return redirect(request.META.get("HTTP_REFERER", "/"))


# ---------------------------------------------------------------------------
# Pattern 3: Trigger client events with HX-Trigger header
# ---------------------------------------------------------------------------

@require_POST
def essay_save(request: HtmxHttpRequest, slug: str) -> HttpResponse:
    """
    Save essay edits and trigger a toast notification on the client.

    trigger_client_event adds to the HX-Trigger response header. The
    client listens for these events to show notifications, update
    counters, or trigger other behavior without additional requests.

    The 'after' parameter controls timing:
      - "receive": fires immediately when response is received (default)
      - "settle": fires after the DOM has settled
      - "swap": fires after the swap is complete
    """
    essay = get_object_or_404(Essay, slug=slug, author=request.user)
    form = EssayForm(request.POST, instance=essay)

    if form.is_valid():
        form.save()
        response = render(
            request,
            "content/partials/essay_form.html",
            {"form": EssayForm(instance=essay), "essay": essay},
        )
        # Trigger a toast notification on the client
        trigger_client_event(
            response,
            "showToast",
            params={"message": "Essay saved.", "level": "success"},
        )
        # Also trigger a word count update in the sidebar
        trigger_client_event(
            response,
            "wordCountUpdated",
            params={"count": essay.word_count},
            after="settle",
        )
        return response

    return render(
        request,
        "content/partials/essay_form.html",
        {"form": form, "essay": essay},
    )


# ---------------------------------------------------------------------------
# Pattern 4: Infinite scroll pagination
# ---------------------------------------------------------------------------

@require_GET
def essay_feed(request: HtmxHttpRequest) -> HttpResponse:
    """
    Infinite scroll feed. Each page returns essay cards plus a hidden
    trigger element that loads the next page when scrolled into view.

    The template partial includes a sentinel div with:
      hx-get="?page={{ page.next_page_number }}"
      hx-trigger="revealed"
      hx-swap="afterend"

    When the sentinel scrolls into the viewport, HTMX fetches the next
    page and appends it after the current batch. The sentinel itself is
    included in each response so the chain continues.
    """
    page_num = request.GET.get("page", "1")
    essays = Essay.objects.published().select_related("author").prefetch_related("tags")
    page = Paginator(essays, 12).get_page(page_num)

    # First request: full page with shell. Subsequent: just the cards.
    template_name = "content/essay_feed.html"
    if request.htmx:
        template_name = "content/partials/essay_feed_page.html"

    return render(request, template_name, {"page": page})


# ---------------------------------------------------------------------------
# Pattern 5: Search-as-you-type with debounce
# ---------------------------------------------------------------------------

@require_GET
def essay_search(request: HtmxHttpRequest) -> HttpResponse:
    """
    Search-as-you-type for essays.

    The search input uses:
      hx-get="/essays/search/"
      hx-trigger="keyup changed delay:300ms"
      hx-target="#search-results"
      hx-indicator="#search-spinner"

    The 300ms delay debounces the request so we do not fire on every
    keystroke. The hx-indicator shows a spinner while the request is
    in flight.

    The view returns only the results partial. If the query is empty,
    it returns the empty state partial.
    """
    query = request.GET.get("q", "").strip()

    if not query:
        return render(request, "content/partials/search_empty.html")

    essays = (
        Essay.objects
        .published()
        .filter(title__icontains=query)
        .select_related("author")[:20]
    )

    # Push the search URL so the browser back button works
    response = render(
        request,
        "content/partials/search_results.html",
        {"essays": essays, "query": query},
    )

    if request.htmx:
        push_url(response, f"/essays/search/?q={query}")

    return response


# ---------------------------------------------------------------------------
# Pattern 6: Form submission returning updated fragment
# ---------------------------------------------------------------------------

@require_http_methods(["GET", "POST"])
def field_note_edit(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """
    Inline editing for a field note.

    GET: Returns the edit form partial (loaded into the row via hx-get).
    POST: Validates and saves, then returns the updated display partial.
          On validation error, returns the form partial with errors.

    The pattern replaces a display row with an edit form, and on
    successful save swaps the form back to the display row.
    """
    note = get_object_or_404(FieldNote, pk=pk, author=request.user)

    if request.method == "GET":
        form = FieldNoteForm(instance=note)
        return render(
            request,
            "content/partials/field_note_form.html",
            {"form": form, "note": note},
        )

    form = FieldNoteForm(request.POST, instance=note)
    if form.is_valid():
        form.save()
        response = render(
            request,
            "content/partials/field_note_row.html",
            {"note": note},
        )
        trigger_client_event(
            response,
            "showToast",
            params={"message": "Note updated.", "level": "success"},
        )
        return response

    # Validation failed: return form with errors
    return render(
        request,
        "content/partials/field_note_form.html",
        {"form": form, "note": note},
    )


# ---------------------------------------------------------------------------
# Pattern 7: Delete with confirmation via hx-confirm
# ---------------------------------------------------------------------------

@require_http_methods(["DELETE"])
def field_note_delete(request: HtmxHttpRequest, pk: int) -> HttpResponse:
    """
    Delete a field note. The template button uses:
      hx-delete="/notes/{{ note.pk }}/delete/"
      hx-confirm="Delete this note? This cannot be undone."
      hx-target="closest tr"
      hx-swap="outerHTML swap:500ms"

    hx-confirm shows a browser confirm dialog before sending the
    request. On success we return an empty response, which replaces
    the table row with nothing (effectively removing it).

    The swap:500ms modifier adds a 500ms settling delay so you can
    apply a fade-out CSS transition before the element is removed.
    """
    note = get_object_or_404(FieldNote, pk=pk, author=request.user)
    note.delete()

    response = HttpResponse("")
    trigger_client_event(
        response,
        "showToast",
        params={"message": "Note deleted.", "level": "info"},
    )
    return response


# ---------------------------------------------------------------------------
# Pattern 8: HttpResponseLocation for partial navigation
# ---------------------------------------------------------------------------

@require_POST
def tag_create(request: HtmxHttpRequest) -> HttpResponse:
    """
    Create a tag from a modal form, then use HttpResponseLocation to
    navigate to the tag page. Unlike HttpResponseClientRedirect,
    HttpResponseLocation uses hx-location behavior: it performs an
    AJAX request to the target URL and swaps the content into the
    specified target, without a full page reload.

    This is ideal for SPA-like navigation where you want to update
    part of the page after a form submission.
    """
    name = request.POST.get("name", "").strip()
    if not name:
        return render(
            request,
            "content/partials/tag_form.html",
            {"error": "Tag name is required."},
        )

    tag, created = Tag.objects.get_or_create(name=name)

    if request.htmx:
        return HttpResponseLocation(
            redirect_to=f"/tags/{tag.slug}/",
            target="#main-content",
            swap="innerHTML",
        )

    return redirect("tags:detail", slug=tag.slug)


# ---------------------------------------------------------------------------
# Pattern 9: Polling with stop
# ---------------------------------------------------------------------------

@require_GET
def essay_export_status(request: HtmxHttpRequest, task_id: str) -> HttpResponse:
    """
    Poll for async export task status.

    The template uses:
      hx-get="/essays/export/{{ task_id }}/status/"
      hx-trigger="every 2s"

    When the task completes, we return HttpResponseStopPolling (status
    code 286) which tells HTMX to stop the polling loop.
    """
    from apps.content.tasks import get_export_status

    status = get_export_status(task_id)

    if status["state"] == "SUCCESS":
        response = render(
            request,
            "content/partials/export_complete.html",
            {"download_url": status["result"]},
        )
        # Return 286 to stop HTMX polling
        return HttpResponseStopPolling(response.content)

    if status["state"] == "FAILURE":
        response = render(
            request,
            "content/partials/export_failed.html",
            {"error": status.get("error", "Export failed.")},
        )
        return HttpResponseStopPolling(response.content)

    # Still in progress
    return render(
        request,
        "content/partials/export_progress.html",
        {"progress": status.get("progress", 0)},
    )


# ---------------------------------------------------------------------------
# Pattern 10: Retarget and reswap from the server
# ---------------------------------------------------------------------------

@require_POST
def essay_quick_create(request: HtmxHttpRequest) -> HttpResponse:
    """
    Quick-create an essay from the dashboard. On success, retarget the
    response to the essay list and reswap to prepend the new item.

    retarget() sets the HX-Retarget header, overriding the hx-target
    attribute from the triggering element. reswap() sets HX-Reswap,
    overriding the swap strategy. This lets the server control where
    and how the response is inserted.
    """
    form = EssayForm(request.POST)
    if form.is_valid():
        essay = form.save(commit=False)
        essay.author = request.user
        essay.save()

        response = render(
            request,
            "content/partials/essay_row.html",
            {"essay": essay},
        )
        retarget(response, "#essay-list")
        reswap(response, "afterbegin")
        trigger_client_event(
            response,
            "showToast",
            params={"message": f"Created: {essay.title}", "level": "success"},
        )
        return response

    # Validation error: return the form with errors in place
    return render(
        request,
        "content/partials/quick_create_form.html",
        {"form": form},
    )
