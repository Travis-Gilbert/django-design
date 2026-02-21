# Django Admin Customization Reference

Django admin is one of the framework's superpowers. For internal tools especially, a well-configured admin can replace an entire custom dashboard.

## Core Principles

- **Register every model** that staff might need to see or edit
- **Use `list_display`** generously to show useful columns at a glance
- **Add `list_filter` and `search_fields`** so staff can find records without writing queries
- **Use `readonly_fields`** for computed or sensitive data
- **Override `get_queryset`** to add annotations or restrict visibility by user
- **Use `fieldsets`** to organize complex model forms into logical sections
- **Custom admin actions** for batch operations (approve, reject, export)

## Standard Registration Pattern

```python
from django.contrib import admin
from django.utils import timezone


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ['address', 'program', 'status', 'assigned_to', 'days_since_purchase']
    list_filter = ['program', 'status', 'assigned_to']
    search_fields = ['address', 'parcel_id', 'buyer__last_name']
    readonly_fields = ['created_at', 'updated_at', 'days_since_purchase']

    fieldsets = [
        ('Property Info', {'fields': ['address', 'parcel_id', 'program']}),
        ('Compliance', {'fields': ['status', 'assigned_to', 'due_date']}),
        ('Timestamps', {'fields': ['created_at', 'updated_at'], 'classes': ['collapse']}),
    ]

    def days_since_purchase(self, obj):
        if obj.purchase_date:
            return (timezone.now().date() - obj.purchase_date).days
        return None
    days_since_purchase.short_description = 'Days Since Purchase'
```

## Custom Admin Actions

```python
@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    actions = ['approve_selected', 'mark_needs_review']

    @admin.action(description='Approve selected applications')
    def approve_selected(self, request, queryset):
        updated = queryset.filter(status='pending').update(
            status='approved',
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )
        self.message_user(request, f'{updated} applications approved.')

    @admin.action(description='Mark as needs review')
    def mark_needs_review(self, request, queryset):
        queryset.update(status='needs_review')
```

## Overriding get_queryset

Restrict visibility or add annotations:

```python
class PropertyAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Add computed annotations
        qs = qs.annotate(
            document_count=Count('documents'),
        )
        # Restrict non-superusers to their assigned properties
        if not request.user.is_superuser:
            qs = qs.filter(assigned_to=request.user)
        return qs

    def document_count(self, obj):
        return obj.document_count
    document_count.admin_order_field = 'document_count'
```

## Inline Models

Show related records on the parent's edit page:

```python
class DocumentInline(admin.TabularInline):
    model = Document
    extra = 0
    readonly_fields = ['uploaded_at', 'file_size']
    fields = ['document_type', 'file', 'uploaded_at', 'file_size']


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    inlines = [DocumentInline]
```

## django-unfold Integration

For modern admin UIs, django-unfold replaces the default admin theme with a Tailwind-based interface:

```python
# settings/base.py
INSTALLED_APPS = [
    'unfold',           # must be before django.contrib.admin
    'unfold.contrib.filters',
    'unfold.contrib.forms',
    'django.contrib.admin',
    ...
]

# admin.py
from unfold.admin import ModelAdmin as UnfoldModelAdmin

@admin.register(Property)
class PropertyAdmin(UnfoldModelAdmin):
    # Same fields as standard ModelAdmin
    list_display = ['address', 'program', 'status']
    # unfold adds: compressed_fields, warn_unsaved_form, etc.
```

Override unfold's primary color in settings:

```python
UNFOLD = {
    "SITE_TITLE": "Application Portal",
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

## Admin Best Practices

- Index every field used in `list_filter` and `search_fields` — unindexed admin filters cause slow queries on large tables
- Use `raw_id_fields` for ForeignKey fields with many records instead of dropdown selects
- Add `date_hierarchy` for date-based models (applications, orders, logs)
- Use `list_per_page` to control pagination (default 100 is usually fine)
- Override `has_delete_permission` to prevent accidental deletions of critical records
- Use `list_select_related` to avoid N+1 queries in list views
