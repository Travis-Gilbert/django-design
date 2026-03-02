"""
Admin action patterns for a content publishing site.

Demonstrates:
- Bulk publish action with confirmation
- Export to CSV action
- Action with intermediate page pattern
- Proper permission checks on actions
- Message framework integration for user feedback

Domain: content publishing site with Essay and FieldNote models.

Note on intermediate pages: Django admin actions normally operate immediately
on the selected queryset. For destructive or high-impact actions, you should
present a confirmation page first. The pattern below shows how to render an
intermediate template and only execute the action when the user confirms.
"""
import csv
import io
from datetime import datetime

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone


# ---------------------------------------------------------------------------
# Simple bulk status actions
# ---------------------------------------------------------------------------

@admin.action(description="Mark selected items as published")
def mark_as_published(modeladmin, request, queryset):
    """
    Bulk-publish selected essays or field notes.

    Sets stage to "published" and records published_at for any item that
    does not already have one. Reports how many items were updated.

    Permission check: only users with the change permission can run this.
    The admin framework already enforces that the user has view permission
    to see the changelist, but actions should verify change permission
    explicitly for destructive or state-changing operations.
    """
    if not modeladmin.has_change_permission(request):
        messages.error(request, "You do not have permission to publish items.")
        return

    now = timezone.now()
    updated = 0
    skipped = 0

    for obj in queryset:
        if obj.stage == "published":
            skipped += 1
            continue
        obj.stage = "published"
        if hasattr(obj, "published_at") and not obj.published_at:
            obj.published_at = now
        obj.save(update_fields=_get_publish_fields(obj))
        updated += 1

    if updated:
        messages.success(
            request,
            f"Successfully published {updated} item(s).",
        )
    if skipped:
        messages.info(
            request,
            f"Skipped {skipped} item(s) already published.",
        )


@admin.action(description="Revert selected items to draft")
def mark_as_draft(modeladmin, request, queryset):
    """Bulk-revert selected items to draft stage."""
    if not modeladmin.has_change_permission(request):
        messages.error(request, "You do not have permission to modify items.")
        return

    count = queryset.exclude(stage="drafting").update(stage="drafting")
    messages.success(request, f"Reverted {count} item(s) to draft.")


@admin.action(description="Send selected items to review (production stage)")
def send_to_review(modeladmin, request, queryset):
    """Move selected items to the production/review stage."""
    if not modeladmin.has_change_permission(request):
        messages.error(request, "You do not have permission to modify items.")
        return

    # Only transition items that are currently in drafting
    eligible = queryset.filter(stage="drafting")
    skipped = queryset.exclude(stage="drafting").count()
    count = eligible.update(stage="production")

    if count:
        messages.success(request, f"Sent {count} item(s) to review.")
    if skipped:
        messages.warning(
            request,
            f"Skipped {skipped} item(s) not in drafting stage.",
        )


def _get_publish_fields(obj):
    """Return the list of fields to update when publishing."""
    fields = ["stage"]
    if hasattr(obj, "published_at"):
        fields.append("published_at")
    return fields


# ---------------------------------------------------------------------------
# Export to CSV action
# ---------------------------------------------------------------------------

@admin.action(description="Export selected essays as CSV")
def export_essays_as_csv(modeladmin, request, queryset):
    """
    Export selected essays to a downloadable CSV file.

    The CSV includes core fields useful for editorial reporting:
    title, author, stage, word count, tags, and dates.

    Pattern notes:
    - Returns an HttpResponse with content_type text/csv so the browser
      triggers a download instead of displaying the response.
    - Uses Python's csv module for proper escaping of commas, quotes,
      and newlines in field values.
    - Streams rows one at a time to keep memory usage constant regardless
      of how many essays are selected.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"essays_export_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Header row
    writer.writerow([
        "Title",
        "Slug",
        "Author",
        "Stage",
        "Word Count",
        "Tags",
        "Created",
        "Updated",
        "Published",
    ])

    # Optimize: prefetch tags to avoid N+1 queries
    essays = queryset.select_related("author").prefetch_related("tags")

    for essay in essays:
        writer.writerow([
            essay.title,
            essay.slug,
            getattr(essay.author, "username", ""),
            essay.stage,
            essay.word_count or "",
            "; ".join(t.name for t in essay.tags.all()),
            _format_date(essay.created_at),
            _format_date(essay.updated_at),
            _format_date(getattr(essay, "published_at", None)),
        ])

    return response


def _format_date(dt):
    """Format a datetime for CSV output, handling None gracefully."""
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Action with intermediate confirmation page
# ---------------------------------------------------------------------------

@admin.action(description="Bulk publish with confirmation")
def bulk_publish_with_confirmation(modeladmin, request, queryset):
    """
    Publish selected essays after showing a confirmation page.

    This pattern is essential for high-impact actions where you want the
    user to review what they are about to do before it happens. The flow:

    1. User selects items and picks the action from the dropdown.
    2. Django calls this function. We detect it is the initial request
       (no "confirm" in POST) and render a confirmation template.
    3. The confirmation template shows the list of items and a form with
       a hidden "confirm" field plus the selected item PKs.
    4. User clicks "Confirm". Django calls this function again, this time
       with "confirm" in POST.
    5. We execute the actual operation and redirect back to the changelist.

    Template location: templates/admin/content/essay/bulk_publish_confirm.html
    The template should extend "admin/base_site.html" for consistent styling.
    """
    if "confirm" in request.POST:
        # Second pass: user confirmed, execute the operation
        if not modeladmin.has_change_permission(request):
            messages.error(
                request,
                "You do not have permission to publish essays.",
            )
            return

        now = timezone.now()
        updated = 0
        for obj in queryset:
            if obj.stage != "published":
                obj.stage = "published"
                if hasattr(obj, "published_at") and not obj.published_at:
                    obj.published_at = now
                obj.save(update_fields=_get_publish_fields(obj))
                updated += 1

        messages.success(
            request,
            f"Published {updated} essay(s).",
        )
        return None  # Returning None redirects to the changelist

    # First pass: show confirmation page
    # Gather data for the confirmation template
    items = queryset.select_related("author")
    already_published = items.filter(stage="published").count()
    to_publish = items.exclude(stage="published").count()

    context = {
        **modeladmin.admin_site.each_context(request),
        "title": "Confirm bulk publish",
        "items": items,
        "already_published_count": already_published,
        "to_publish_count": to_publish,
        "action_name": "bulk_publish_with_confirmation",
        "opts": modeladmin.model._meta,
        "media": modeladmin.media,
    }

    return render(
        request,
        "admin/content/essay/bulk_publish_confirm.html",
        context,
    )


# ---------------------------------------------------------------------------
# Action with intermediate form (advanced pattern)
# ---------------------------------------------------------------------------

@admin.action(description="Reassign selected essays to another author")
def reassign_author(modeladmin, request, queryset):
    """
    Reassign selected essays to a different author via an intermediate form.

    This extends the confirmation pattern by adding a form field (author
    selection) to the intermediate page. The user selects items, picks
    this action, then chooses the target author on the intermediate page.

    Template location: templates/admin/content/essay/reassign_author.html

    This pattern is useful any time an action needs additional input
    beyond just "are you sure?", for example:
    - Reassigning items to a different owner
    - Setting a scheduled publish date for a batch
    - Choosing an export format
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()

    if "new_author" in request.POST:
        # Second pass: form was submitted with a new author selection
        new_author_id = request.POST.get("new_author")
        if not new_author_id:
            messages.error(request, "Please select an author.")
            # Fall through to show the form again
        else:
            try:
                new_author = User.objects.get(pk=new_author_id)
            except User.DoesNotExist:
                messages.error(request, "Selected author does not exist.")
                return

            count = queryset.update(author=new_author)
            messages.success(
                request,
                f"Reassigned {count} essay(s) to {new_author.username}.",
            )
            return None  # Redirect to changelist

    # First pass (or failed validation): show the intermediate form
    # Get authors who are staff (eligible to own essays)
    authors = User.objects.filter(is_staff=True).order_by("username")

    context = {
        **modeladmin.admin_site.each_context(request),
        "title": "Reassign essays to author",
        "items": queryset.select_related("author"),
        "authors": authors,
        "item_count": queryset.count(),
        "action_name": "reassign_author",
        "opts": modeladmin.model._meta,
        "media": modeladmin.media,
    }

    return render(
        request,
        "admin/content/essay/reassign_author.html",
        context,
    )


# ---------------------------------------------------------------------------
# Confirmation template example (inline for reference)
# ---------------------------------------------------------------------------

BULK_PUBLISH_CONFIRM_TEMPLATE = """
{# templates/admin/content/essay/bulk_publish_confirm.html #}
{# This is shown here as a reference. Save it as an actual template file. #}

{% extends "admin/base_site.html" %}
{% load i18n %}

{% block title %}Confirm Bulk Publish{% endblock %}

{% block content %}
<form method="post">
    {% csrf_token %}

    <h2>Confirm publication of {{ to_publish_count }} essay(s)</h2>

    {% if already_published_count %}
    <p class="help">
        {{ already_published_count }} selected essay(s) are already published
        and will be skipped.
    </p>
    {% endif %}

    <table>
        <thead>
            <tr>
                <th>Title</th>
                <th>Author</th>
                <th>Current Stage</th>
            </tr>
        </thead>
        <tbody>
            {% for item in items %}
            <tr>
                <td>{{ item.title }}</td>
                <td>{{ item.author }}</td>
                <td>{{ item.stage }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    {# Pass the selected PKs back to the action #}
    {% for item in items %}
    <input type="hidden" name="_selected_action" value="{{ item.pk }}" />
    {% endfor %}
    <input type="hidden" name="action" value="{{ action_name }}" />
    <input type="hidden" name="confirm" value="1" />

    <div style="margin-top: 20px;">
        <input type="submit" value="Confirm Publish" class="default" />
        <a href="{% url 'admin:content_essay_changelist' %}"
           style="margin-left: 10px;">Cancel</a>
    </div>
</form>
{% endblock %}
"""

REASSIGN_AUTHOR_TEMPLATE = """
{# templates/admin/content/essay/reassign_author.html #}
{# This is shown here as a reference. Save it as an actual template file. #}

{% extends "admin/base_site.html" %}
{% load i18n %}

{% block title %}Reassign Author{% endblock %}

{% block content %}
<form method="post">
    {% csrf_token %}

    <h2>Reassign {{ item_count }} essay(s) to a new author</h2>

    <div style="margin: 20px 0;">
        <label for="new_author"><strong>New author:</strong></label>
        <select name="new_author" id="new_author">
            <option value="">-- Select author --</option>
            {% for author in authors %}
            <option value="{{ author.pk }}">
                {{ author.username }} ({{ author.get_full_name }})
            </option>
            {% endfor %}
        </select>
    </div>

    <h3>Essays to reassign:</h3>
    <ul>
        {% for item in items %}
        <li>{{ item.title }} (currently: {{ item.author }})</li>
        {% endfor %}
    </ul>

    {% for item in items %}
    <input type="hidden" name="_selected_action" value="{{ item.pk }}" />
    {% endfor %}
    <input type="hidden" name="action" value="{{ action_name }}" />

    <div style="margin-top: 20px;">
        <input type="submit" value="Reassign" class="default" />
        <a href="{% url 'admin:content_essay_changelist' %}"
           style="margin-left: 10px;">Cancel</a>
    </div>
</form>
{% endblock %}
"""
