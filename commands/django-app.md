---
description: Scaffold a new Django app inside an existing project with proper wiring
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
argument-hint: (interactive — no arguments needed)
---

# Django App Scaffold

Guide the user through adding a well-structured app to an existing Django project. This handles the boilerplate that is easy to get wrong: app naming, directory placement, URL wiring, INSTALLED_APPS registration, and test scaffolding.

## Phase 1: Discovery

Before creating anything, understand the existing project structure.

### Step 1: Detect Project Layout

```bash
# Find the project root (where manage.py lives)
find . -name "manage.py" -maxdepth 3

# Find the settings module
grep -r "DJANGO_SETTINGS_MODULE" . --include="*.py" -l | head -5
grep -r "INSTALLED_APPS" . --include="*.py" -l | head -5

# Check if apps/ directory exists
ls -la apps/ 2>/dev/null || echo "No apps/ directory found"

# List existing apps
find . -name "apps.py" -not -path "*/venv/*" -not -path "*/.venv/*" | head -20
```

### Step 2: Ask About the New App

Use AskUserQuestion to gather requirements in a single batch:

1. **App name** — What should this app be called? (Will be converted to snake_case. Examples: `properties`, `compliance`, `notifications`, `user_profiles`)
2. **Domain** — What does this app handle? Describe the real-world process. (e.g., "Tracks property compliance documents and deadlines", "Manages buyer applications and review workflow")
3. **Models** — Based on the domain, suggest 2-4 models and ask the user to confirm or adjust. Include field suggestions.
4. **API or Templates** — Will this app serve a REST API (DRF serializers + viewsets), server-rendered templates (views + forms), or both?
5. **Admin** — Should models be registered in admin? (Default: yes)

## Phase 2: Generate the App

### Step 1: Create the App Directory

Determine placement based on project structure:

```bash
# If apps/ directory exists, create inside it
if [ -d "apps" ]; then
    mkdir -p apps/<app_name>
    python manage.py startapp <app_name> apps/<app_name>
else
    # Create at project root level
    python manage.py startapp <app_name>
fi
```

### Step 2: Fix apps.py

The `name` in `AppConfig` must match how the app is registered in `INSTALLED_APPS`.

```python
# apps/<app_name>/apps.py (if inside apps/ directory)
from django.apps import AppConfig


class <AppNameConfig>(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.<app_name>'
    verbose_name = '<Human Readable Name>'
```

### Step 3: Register in INSTALLED_APPS

Read the current settings file and add the new app:

```python
# In settings/base.py or settings.py
INSTALLED_APPS = [
    # ...
    'apps.<app_name>',  # or just '<app_name>' if not in apps/ directory
]
```

### Step 4: Create the File Structure

Based on the user's answers, create the appropriate files:

**Always create:**
```
<app_name>/
    __init__.py       # (created by startapp)
    apps.py           # (fix the name)
    models.py         # populated with models
    admin.py          # populated with registrations
    urls.py           # new file with app_name and urlpatterns
    tests/
        __init__.py
        test_models.py
        test_views.py
        factories.py
```

**If REST API:**
```
    serializers.py
    viewsets.py       # or views.py with DRF views
```

**If server-rendered templates:**
```
    forms.py
    views.py
    templates/<app_name>/
        list.html
        detail.html
        form.html
```

**If the domain suggests complex business logic:**
```
    services.py       # for logic spanning multiple models or external APIs
```

### Step 5: Create urls.py

```python
# apps/<app_name>/urls.py
from django.urls import path, include

app_name = '<app_name>'

urlpatterns = [
    # URL patterns will be added as views are created
]
```

For DRF apps:
```python
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import viewsets

app_name = '<app_name>'

router = DefaultRouter()
# router.register(r'<resource>', viewsets.<Model>ViewSet, basename='<resource>')

urlpatterns = [
    path('', include(router.urls)),
]
```

### Step 6: Wire URLs into the Project

Find the root `urls.py` and add the include:

```python
# project_name/urls.py
urlpatterns = [
    # ... existing patterns
    path('<app_name>/', include('apps.<app_name>.urls', namespace='<app_name>')),
    # or for API apps:
    path('api/v1/<app_name>/', include('apps.<app_name>.urls', namespace='<app_name>')),
]
```

### Step 7: Generate Models

Based on the user's confirmed model list, generate `models.py`:

- Import `TimeStampedModel` from `apps.core.models` if it exists
- Add proper field types based on the domain
- Include `db_index=True` on fields that will be filtered frequently
- Add `Meta` with `ordering`, `indexes`, and `constraints` where appropriate
- Add `__str__` method on every model
- Add custom managers if the domain suggests common query patterns
- Use `TextChoices` for status fields

### Step 8: Generate Admin

Register every model with useful `list_display`, `list_filter`, and `search_fields`:

```python
from django.contrib import admin
from .models import <Model>


@admin.register(<Model>)
class <Model>Admin(admin.ModelAdmin):
    list_display = ['__str__', '<key_field>', '<status_field>', 'created_at']
    list_filter = ['<status_field>', '<category_field>']
    search_fields = ['<text_field>', '<related>__<field>']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = ['<fk_field>']
```

### Step 9: Generate Test Scaffolding

Create factory_boy factories:

```python
# tests/factories.py
import factory
from ..<app_name>.models import <Model>


class <Model>Factory(factory.django.DjangoModelFactory):
    class Meta:
        model = <Model>

    <field> = factory.Faker('<faker_provider>')
    # ...
```

Create initial test files:

```python
# tests/test_models.py
from django.test import TestCase
from .factories import <Model>Factory


class Test<Model>(TestCase):
    def test_str(self):
        instance = <Model>Factory()
        self.assertIsNotNone(str(instance))

    def test_creation(self):
        instance = <Model>Factory()
        self.assertIsNotNone(instance.pk)
```

### Step 10: Run Checks

```bash
python manage.py check
python manage.py makemigrations <app_name>
python manage.py showmigrations <app_name>
```

Do NOT run `migrate` yet. Let the user review the migration first.

## Phase 3: Summary

After generating, present:

1. **Files created** — list every new file and what it contains
2. **Files modified** — what was changed in settings and root urls
3. **Models** — summary of models and their key fields
4. **Next steps** — review the migration, run migrate, create views/serializers

```
App 'properties' created successfully!

Files created:
  apps/properties/models.py      — Property, ComplianceDocument models
  apps/properties/admin.py       — Admin registrations with list_display
  apps/properties/urls.py        — URL conf with app_name namespace
  apps/properties/serializers.py — DRF serializers
  apps/properties/viewsets.py    — DRF viewsets
  apps/properties/tests/         — Test scaffolding with factories

Files modified:
  project_name/settings/base.py  — Added 'apps.properties' to INSTALLED_APPS
  project_name/urls.py           — Added API URL include

Next steps:
  1. Review the generated migration: python manage.py showmigrations
  2. Run the migration: python manage.py migrate
  3. Start building views and business logic
```
