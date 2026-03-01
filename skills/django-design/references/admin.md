# Django Admin Customization Reference

Django admin is one of the framework's superpowers. For internal tools especially, a well-configured admin can replace an entire custom dashboard.

## Core Principles

- **Register every model** that staff might need to see or edit
- **Use `list_display`** generously to show useful columns at a glance
- **Add `list_filter` and `search_fields`** so staff can find records without writing queries
- **Use `readonly_fields`** for computed or sensitive data
- **Override `get_queryset`** to add annotations or restrict visibility by user
- **Use `fieldsets`** to organize complex model forms into logical sections
- **Custom admin actions** for batch operations (publish, archive, export)

## Standard Registration Pattern

```python
from django.contrib import admin
from django.utils import timezone


@admin.register(Essay)
class EssayAdmin(admin.ModelAdmin):
    list_display = ['title', 'stage', 'draft', 'date', 'source_count_display']
    list_filter = ['stage', 'draft', 'date']
    search_fields = ['title', 'slug', 'summary']
    readonly_fields = ['created_at', 'updated_at', 'source_count_display']
    list_select_related = []
    prepopulated_fields = {'slug': ('title',)}

    fieldsets = [
        ('Content', {'fields': ['title', 'slug', 'summary', 'body', 'thesis']}),
        ('Publishing', {'fields': ['stage', 'draft', 'date', 'tags']}),
        ('Metadata', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def source_count_display(self, obj):
        return obj.source_count or 0
    source_count_display.short_description = 'Sources'
```

## Custom Admin Actions

```python
@admin.register(Essay)
class EssayAdmin(admin.ModelAdmin):
    actions = ['publish_selected', 'mark_as_draft', 'export_to_csv']

    @admin.action(description='Publish selected essays')
    def publish_selected(self, request, queryset):
        updated = queryset.filter(stage__in=['drafting', 'production']).update(
            stage='published',
            draft=False,
        )
        self.message_user(request, f'{updated} essays published.')

    @admin.action(description='Revert to draft')
    def mark_as_draft(self, request, queryset):
        queryset.update(draft=True)

    @admin.action(description='Export selected to CSV')
    def export_to_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="essays.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Title', 'Stage', 'Date'])
        for essay in queryset:
            writer.writerow([essay.id, essay.title, essay.stage, essay.date])
        return response
```

## Overriding get_queryset

Restrict visibility or add annotations:

```python
class EssayAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Add computed annotations
        qs = qs.annotate(
            linked_source_count=Count('sources'),
        )
        # Restrict non-superusers to their own drafts
        if not request.user.is_superuser:
            qs = qs.filter(draft=True)
        return qs

    def linked_source_count(self, obj):
        return obj.linked_source_count
    linked_source_count.admin_order_field = 'linked_source_count'
```

## Inline Models

Show related records on the parent's edit page:

```python
class VideoSceneInline(admin.TabularInline):
    model = VideoScene
    extra = 0
    readonly_fields = ['word_count', 'estimated_seconds']
    fields = ['order', 'title', 'scene_type', 'script_text', 'word_count', 'estimated_seconds']


class VideoDeliverableInline(admin.StackedInline):
    """Use StackedInline for models with TextField or many fields."""
    model = VideoDeliverable
    extra = 0
    readonly_fields = ['approved']

    def has_delete_permission(self, request, obj=None):
        return False  # deliverables are append-only


@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    inlines = [VideoSceneInline, VideoDeliverableInline]
```

## Custom Admin Views

For operations that go beyond simple CRUD - intermediate confirmation pages, reports, or dashboards:

```python
from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path


@admin.register(Essay)
class EssayAdmin(admin.ModelAdmin):

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'content-report/',
                self.admin_site.admin_view(self.content_report_view),
                name='content_essay_content_report',
            ),
        ]
        return custom_urls + urls

    def content_report_view(self, request):
        """Custom admin view for content pipeline summary dashboard."""
        from django.db.models import Count, Q

        stats = Essay.objects.aggregate(
            total=Count('id'),
            research=Count('id', filter=Q(stage='research')),
            drafting=Count('id', filter=Q(stage='drafting')),
            published=Count('id', filter=Q(stage='published')),
        )
        by_stage = (
            Essay.objects.values('stage')
            .annotate(count=Count('id'), drafts=Count('id', filter=Q(draft=True)))
            .order_by('-count')
        )

        context = {
            **self.admin_site.each_context(request),
            'title': 'Content Pipeline Report',
            'stats': stats,
            'by_stage': by_stage,
        }
        return TemplateResponse(request, 'admin/content/content_report.html', context)
```

### Intermediate Action Pages

For actions that need user input before executing (e.g., selecting a reason for unpublishing):

```python
@admin.register(Essay)
class EssayAdmin(admin.ModelAdmin):
    actions = ['unpublish_with_reason']

    @admin.action(description='Unpublish with reason')
    def unpublish_with_reason(self, request, queryset):
        if 'apply' in request.POST:
            reason = request.POST.get('reason', '')
            updated = queryset.update(stage='drafting', draft=True)
            self.message_user(request, f'{updated} essays unpublished.')
            return None

        return TemplateResponse(
            request,
            'admin/content/unpublish_intermediate.html',
            {
                'title': 'Unpublish Essays',
                'queryset': queryset,
                'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
            },
        )
```

## Admin Performance

### Avoiding N+1 in List Views

```python
@admin.register(VideoProject)
class VideoProjectAdmin(admin.ModelAdmin):
    list_display = ['title', 'phase', 'scene_count']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Annotate for computed columns to avoid per-row queries
        return qs.annotate(scene_count=Count('scenes'))

    def scene_count(self, obj):
        return obj.scene_count
    scene_count.admin_order_field = 'scene_count'
```

### Autocomplete for Large Foreign Key Tables

```python
# The related model's admin must define search_fields
@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    search_fields = ['title', 'creator', 'url']


@admin.register(SourceLink)
class SourceLinkAdmin(admin.ModelAdmin):
    # Renders as AJAX autocomplete instead of a dropdown with 10,000 options
    autocomplete_fields = ['source']
```

### Controlling Changelist Queries

```python
@admin.register(Essay)
class EssayAdmin(admin.ModelAdmin):
    list_per_page = 50          # default is 100
    show_full_result_count = False  # skip the COUNT(*) on large tables

    # Only show filters that are useful and indexed
    list_filter = [
        'stage',                # must have db_index=True
        'draft',                # boolean, indexed
        ('date', admin.DateFieldListFilter),
    ]
```

## django-unfold Integration

For modern admin UIs, django-unfold replaces the default admin theme with a Tailwind-based interface.

### Setup

```python
# settings/base.py
INSTALLED_APPS = [
    'unfold',           # must be before django.contrib.admin
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    # ...
]

UNFOLD = {
    "SITE_TITLE": "Content Studio",
    "COLORS": {
        "primary": {
            "50": "#f0fdf4",
            "100": "#dcfce7",
            "500": "#2e7d32",
            "600": "#2b6553",
            "700": "#15803d",
        },
    },
}
```

### Unfold ModelAdmin Features

```python
from unfold.admin import ModelAdmin as UnfoldModelAdmin
from unfold.decorators import display


@admin.register(Essay)
class EssayAdmin(UnfoldModelAdmin):
    list_display = ['title', 'display_stage', 'draft', 'date']

    # Unfold-specific: colored status badges in list view
    @display(
        description='Stage',
        ordering='stage',
        label={
            'research': 'warning',
            'drafting': 'info',
            'production': 'info',
            'published': 'success',
        },
    )
    def display_stage(self, obj):
        return obj.stage

    # Unfold-specific: compress fields into rows
    fieldsets = [
        ('Content', {
            'fields': [
                ('title', 'slug'),          # same row
                ('stage', 'draft'),          # same row
            ],
        }),
    ]

    # Unfold-specific: warn before leaving with unsaved changes
    warn_unsaved_form = True
```

### Unfold Navigation Sidebar

```python
# settings/base.py
UNFOLD = {
    "SITE_TITLE": "Content Studio",
    "NAVIGATION": [
        {
            "title": "Content",
            "icon": "article",
            "items": [
                {"title": "Essays", "link": "/admin/content/essay/"},
                {"title": "Field Notes", "link": "/admin/content/fieldnote/"},
                {"title": "Content Report", "link": "/admin/content/essay/content-report/"},
            ],
        },
        {
            "title": "Video",
            "icon": "videocam",
            "items": [
                {"title": "Video Projects", "link": "/admin/content/videoproject/"},
            ],
        },
        {
            "title": "Research",
            "icon": "science",
            "items": [
                {"title": "Sources", "link": "/admin/research/source/"},
                {"title": "Threads", "link": "/admin/research/researchthread/"},
            ],
        },
    ],
}
```

## Custom AdminSite

For projects with multiple admin interfaces (e.g., content studio vs research dashboard):

```python
# apps/core/admin.py
from django.contrib import admin


class ResearchAdminSite(admin.AdminSite):
    site_header = 'Research Dashboard'
    site_title = 'Research'
    index_title = 'Research Overview'

    def has_permission(self, request):
        return request.user.is_active and request.user.has_perm('research.view_source')


research_admin = ResearchAdminSite(name='research')

# Register only research-relevant models
from apps.research.models import Source, ResearchThread
research_admin.register(Source, SourceAdmin)
research_admin.register(ResearchThread, ResearchThreadAdmin)

# urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('research/', research_admin.urls),
]
```

## Admin Best Practices

- Index every field used in `list_filter` and `search_fields` - unindexed admin filters cause slow queries on large tables
- Use `autocomplete_fields` (not `raw_id_fields`) for ForeignKey fields with many records - better UX with search
- Add `date_hierarchy` for date-based models (essays, field notes, sources)
- Use `list_per_page` to control pagination (default 100 is usually fine)
- Override `has_delete_permission` to prevent accidental deletions of published content
- Use `list_select_related` to avoid N+1 queries in list views
- Set `show_full_result_count = False` on tables with 100K+ rows to skip expensive COUNT(*)
- Use `save_on_top = True` for models with many fields so save buttons appear at the top
