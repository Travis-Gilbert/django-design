"""
Admin configuration patterns for a content publishing site.

Demonstrates:
- ModelAdmin with list_display, list_filter, search_fields, list_editable
- Fieldsets and collapsible sections
- TabularInline and StackedInline
- Custom admin actions (mark_as_published, export_as_csv)
- readonly_fields and computed fields
- autocomplete_fields for ForeignKey/M2M
- Custom list_filter with SimpleListFilter
- get_queryset override for annotation
- save_model override
- Custom change_list template override
- Admin date hierarchy
- Prepopulated fields (slug from title)

Domain: content publishing site with Essay, Tag, FieldNote, and related models.
"""
import csv

from django.contrib import admin
from django.db.models import Count, Q
from django.http import HttpResponse
from django.template.defaultfilters import truncatewords
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .actions import (
    export_essays_as_csv,
    mark_as_published,
    mark_as_draft,
    send_to_review,
)
from .forms import EssayAdminForm, FieldNoteAdminForm
from .models import Essay, EssayImage, FieldNote, FieldNoteLink, Tag


# ---------------------------------------------------------------------------
# Custom list filters
# ---------------------------------------------------------------------------

class PublicationStageFilter(admin.SimpleListFilter):
    """
    Filter essays by their stage in the publishing pipeline.

    Uses SimpleListFilter instead of a direct field filter because the
    display labels differ from stored values and we add a compound
    "in progress" lookup that spans multiple statuses.
    """
    title = "publication stage"
    parameter_name = "stage"

    def lookups(self, request, model_admin):
        return [
            ("research", "Research"),
            ("drafting", "Drafting"),
            ("production", "Production"),
            ("published", "Published"),
            ("in_progress", "In Progress (any non-published)"),
        ]

    def queryset(self, request, queryset):
        value = self.value()
        if value == "in_progress":
            return queryset.exclude(stage="published")
        if value:
            return queryset.filter(stage=value)
        return queryset


class WordCountRangeFilter(admin.SimpleListFilter):
    """
    Filter essays by approximate word count ranges.

    Useful for editors scanning for short-form vs long-form content.
    """
    title = "word count"
    parameter_name = "word_count_range"

    def lookups(self, request, model_admin):
        return [
            ("short", "Short (under 500)"),
            ("medium", "Medium (500 - 1500)"),
            ("long", "Long (1500 - 4000)"),
            ("feature", "Feature (4000+)"),
        ]

    def queryset(self, request, queryset):
        ranges = {
            "short": (0, 500),
            "medium": (500, 1500),
            "long": (1500, 4000),
            "feature": (4000, None),
        }
        bounds = ranges.get(self.value())
        if bounds is None:
            return queryset
        low, high = bounds
        qs = queryset.filter(word_count__gte=low)
        if high is not None:
            qs = qs.filter(word_count__lt=high)
        return qs


class HasFeaturedImageFilter(admin.SimpleListFilter):
    """Filter to show essays that do or do not have a featured image."""
    title = "featured image"
    parameter_name = "has_image"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Has featured image"),
            ("no", "No featured image"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.exclude(featured_image="")
        if self.value() == "no":
            return queryset.filter(
                Q(featured_image="") | Q(featured_image__isnull=True)
            )
        return queryset


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------

class EssayImageInline(admin.TabularInline):
    """
    TabularInline for images attached to an essay.

    TabularInline works well here because each image row is compact:
    just a file, caption, alt text, and sort order.
    """
    model = EssayImage
    extra = 1
    min_num = 0
    max_num = 20
    fields = ("image", "caption", "alt_text", "sort_order")
    ordering = ("sort_order",)

    # Show a thumbnail in readonly mode after the image is saved
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 60px;" />',
                obj.image.url,
            )
        return "-"
    image_preview.short_description = "Preview"

    def get_fields(self, request, obj=None):
        """Add preview column only when editing an existing essay."""
        fields = list(super().get_fields(request, obj))
        if obj is not None:
            fields.append("image_preview")
        return fields


class FieldNoteLinkInline(admin.StackedInline):
    """
    StackedInline for links attached to a field note.

    StackedInline is better than TabularInline here because each link
    has a URL, a title, a description, and a link type, so enough fields
    that a horizontal row would be cramped.
    """
    model = FieldNoteLink
    extra = 0
    min_num = 0
    max_num = 10
    fields = ("url", "title", "description", "link_type")
    classes = ("collapse",)  # Collapsed by default to reduce visual noise


# ---------------------------------------------------------------------------
# Tag admin (simple model, minimal config)
# ---------------------------------------------------------------------------

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "essay_count")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)

    def get_queryset(self, request):
        """Annotate with essay count to avoid N+1 in list_display."""
        qs = super().get_queryset(request)
        return qs.annotate(_essay_count=Count("essays"))

    def essay_count(self, obj):
        return obj._essay_count
    essay_count.admin_order_field = "_essay_count"
    essay_count.short_description = "Essays"


# ---------------------------------------------------------------------------
# Essay admin (full-featured)
# ---------------------------------------------------------------------------

@admin.register(Essay)
class EssayAdmin(admin.ModelAdmin):
    """
    Full-featured ModelAdmin demonstrating most customization points.

    Key patterns:
    - Fieldsets group related fields and use collapsible sections for
      metadata that editors rarely touch.
    - list_display mixes model fields with computed callables.
    - get_queryset annotates to prevent N+1 queries in the changelist.
    - save_model sets the published_at timestamp when stage changes.
    - A custom change_list_template adds a summary banner.
    """

    # -- Form configuration --------------------------------------------------
    form = EssayAdminForm

    fieldsets = (
        (None, {
            "fields": ("title", "slug", "subtitle", "author"),
            "description": "Core identity fields for this essay.",
        }),
        ("Content", {
            "fields": ("body", "excerpt"),
        }),
        ("Classification", {
            "fields": ("tags", "stage", "featured_image"),
        }),
        ("Metadata", {
            "fields": (
                "word_count",
                "reading_time_display",
                "created_at",
                "updated_at",
                "published_at",
            ),
            "classes": ("collapse",),
            "description": "Auto-populated fields. Expand to inspect.",
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description"),
            "classes": ("collapse",),
        }),
    )

    # -- List view configuration ---------------------------------------------
    list_display = (
        "title",
        "author",
        "stage",
        "tag_list",
        "word_count",
        "reading_time_display",
        "updated_at",
        "is_published",
    )
    list_display_links = ("title",)
    list_editable = ("stage",)
    list_filter = (
        PublicationStageFilter,
        WordCountRangeFilter,
        HasFeaturedImageFilter,
        "author",
        "tags",
    )
    search_fields = (
        "title",        # icontains by default
        "=slug",        # exact match
        "body",         # icontains
        "author__username",
        "author__email",
    )
    list_per_page = 25
    list_select_related = ("author",)
    date_hierarchy = "created_at"
    ordering = ("-updated_at",)

    # -- Field-level configuration -------------------------------------------
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "tags")
    readonly_fields = (
        "word_count",
        "reading_time_display",
        "created_at",
        "updated_at",
        "published_at",
    )

    # -- Inlines -------------------------------------------------------------
    inlines = [EssayImageInline]

    # -- Actions -------------------------------------------------------------
    actions = [
        mark_as_published,
        mark_as_draft,
        send_to_review,
        export_essays_as_csv,
    ]

    # -- Custom template (optional) ------------------------------------------
    # Uncomment to use a custom change_list template that adds a stats banner.
    # The template should extend "admin/change_list.html" and override the
    # "content_title" or "result_list" blocks.
    #
    # change_list_template = "admin/content/essay/change_list.html"

    # -- Computed fields for list_display ------------------------------------

    @admin.display(description="Tags", ordering="title")
    def tag_list(self, obj):
        """
        Display comma-separated tag names.

        Uses prefetch_related in get_queryset to avoid N+1.
        """
        return ", ".join(t.name for t in obj.tags.all())

    @admin.display(
        description="Reading time",
        ordering="word_count",
    )
    def reading_time_display(self, obj):
        """Estimate reading time at 250 words per minute."""
        if not obj.word_count:
            return "-"
        minutes = max(1, round(obj.word_count / 250))
        return f"{minutes} min"

    @admin.display(description="Published", boolean=True)
    def is_published(self, obj):
        return obj.stage == "published"

    # -- QuerySet optimization -----------------------------------------------

    def get_queryset(self, request):
        """
        Optimize the changelist query.

        - select_related for author (ForeignKey shown in list_display)
        - prefetch_related for tags (M2M shown via tag_list callable)

        Without these, every row in the changelist fires extra queries.
        Always profile your admin changelist with django-debug-toolbar
        and add select_related / prefetch_related as needed.
        """
        qs = super().get_queryset(request)
        return qs.select_related("author").prefetch_related("tags")

    # -- save_model override -------------------------------------------------

    def save_model(self, request, obj, form, change):
        """
        Set published_at when an essay transitions to published stage.

        Important: keep business logic minimal here. If you find yourself
        writing more than a few lines, move the logic to the model's save()
        method or a service function. The admin should only handle
        admin-specific concerns (like tracking who made the change).
        """
        if change:
            old_stage = Essay.objects.filter(pk=obj.pk).values_list(
                "stage", flat=True
            ).first()
            if old_stage != "published" and obj.stage == "published":
                obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)

    # -- Media for custom admin JS/CSS (optional) ----------------------------

    class Media:
        css = {
            "all": ("admin/css/custom_essay_admin.css",),
        }
        js = ("admin/js/word_count_live.js",)


# ---------------------------------------------------------------------------
# FieldNote admin
# ---------------------------------------------------------------------------

@admin.register(FieldNote)
class FieldNoteAdmin(admin.ModelAdmin):
    """
    Simpler admin for short-form field notes.

    Demonstrates a more minimal configuration compared to EssayAdmin.
    """
    form = FieldNoteAdminForm

    fieldsets = (
        (None, {
            "fields": ("title", "slug", "author", "body"),
        }),
        ("Classification", {
            "fields": ("tags", "stage"),
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    list_display = (
        "title",
        "author",
        "stage",
        "body_preview",
        "created_at",
    )
    list_filter = ("stage", "author", "tags")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("author", "tags")
    readonly_fields = ("created_at", "updated_at")
    list_select_related = ("author",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    inlines = [FieldNoteLinkInline]

    actions = [mark_as_published, mark_as_draft]

    @admin.display(description="Preview")
    def body_preview(self, obj):
        """Show a truncated preview of the note body in the changelist."""
        return truncatewords(obj.body, 15)
