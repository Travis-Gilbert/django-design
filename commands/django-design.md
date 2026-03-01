---
description: Scaffold a new Django project with production-grade structure
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
argument-hint: (interactive — no arguments needed)
---

# Django Project Scaffold

Guide the user through creating a well-architected Django project. This is an interactive process — ask questions, then generate the project structure.

## Phase 1: Discovery

Use the AskUserQuestion tool to gather project requirements. Ask these questions in 1-2 batches (not all at once):

**Batch 1 — Identity and Domain:**

1. **Project name** — What should the project be called? (used for directory name and Django project name; will be converted to snake_case for Python)
2. **Domain** — What does this application do? What real-world process does it model? (e.g., "content publishing studio", "inventory management system", "customer support ticketing")
3. **Scale** — Is this a small internal tool, a medium business application, or a large public-facing portal?

**Batch 2 — Technical Decisions:**

4. **Apps** — Based on the domain description, suggest 2-4 Django apps and ask if the user wants to adjust. Always include a `core` app.
5. **Auth approach** — Does this need user authentication? Options: Django built-in auth, external provider (Clerk, Auth0), token-based API auth, or no auth needed.
6. **API** — Will this serve a REST API (DRF), server-rendered templates (Django templates + HTMX), or both?
7. **Deployment target** — Where will this deploy? Options: Railway, Vercel, Docker, traditional VPS, or undecided.
8. **Database** — PostgreSQL (recommended), SQLite (development only), or other?

## Phase 2: Generate Project

After gathering answers, create the project:

### Step 1: Create Django project

```bash
# Check if django-admin is available
which django-admin || pip install django

# Create the project (use snake_case for project name)
django-admin startproject <project_name> .
```

If the user is already in an empty directory, create in place with `.`. If not, create a subdirectory.

### Step 2: Restructure settings

Convert the single `settings.py` into a settings package:

```
<project_name>/settings/
    __init__.py        # from .base import *; detect environment
    base.py            # move original settings.py content here
    development.py     # DEBUG=True, local DB, django-debug-toolbar
    production.py      # security settings, external DB
    test.py            # fast passwords, in-memory cache
```

**settings/__init__.py content:**
```python
import os

environment = os.environ.get('DJANGO_ENV', 'development')

if environment == 'production':
    from .production import *
elif environment == 'test':
    from .test import *
else:
    from .development import *
```

### Step 3: Create apps directory and apps

```bash
mkdir -p apps/core
```

For each app the user confirmed:
```bash
mkdir -p apps/<app_name>
python manage.py startapp <app_name> apps/<app_name>
```

Fix each app's `apps.py` to use the correct name:
```python
class <AppName>Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.<app_name>'
```

### Step 4: Create core app base models

In `apps/core/models.py`, create:

```python
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base providing created_at and updated_at fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
```

### Step 5: Create directory structure

```
templates/
    base.html
    <app_name>/
static/
    css/
    js/
requirements/
    base.txt
    development.txt
    production.txt
```

### Step 6: Configure base.py

Update `base.py` with:
- Add `apps/` to Python path or configure `INSTALLED_APPS` with `apps.` prefix
- Register all created apps in `INSTALLED_APPS`
- Set `AUTH_USER_MODEL = 'core.User'` (if auth is needed)
- Configure `TEMPLATES` with the `templates/` directory
- Configure `STATICFILES_DIRS` with the `static/` directory
- Set `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'`

### Step 7: Configure development.py

```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

If PostgreSQL was chosen, use `dj-database-url` instead.

### Step 8: Configure production.py

Include the security settings checklist from the django-design skill:
- `SECURE_SSL_REDIRECT = True`
- `SESSION_COOKIE_SECURE = True`
- `CSRF_COOKIE_SECURE = True`
- `SECURE_HSTS_SECONDS = 31536000`
- Database via `dj-database-url` or `DATABASE_URL`
- `SECRET_KEY` from environment variable
- `DEBUG = False`

### Step 9: Create requirements files

**requirements/base.txt:**
```
Django>=5.1,<6.1
```

Add based on user choices:
- DRF: `djangorestframework`
- PostgreSQL: `psycopg2-binary`, `dj-database-url`
- External auth: relevant packages
- Environment vars: `django-environ`

**requirements/development.txt:**
```
-r base.txt
django-debug-toolbar
factory-boy
pytest-django
```

**requirements/production.txt:**
```
-r base.txt
gunicorn
whitenoise
```

Add deployment-specific packages based on target.

### Step 10: Create .env.example and .gitignore

**.env.example:**
```
DJANGO_ENV=development
SECRET_KEY=change-me-to-a-real-secret-key
DATABASE_URL=postgres://user:pass@localhost:5432/dbname
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

**.gitignore** (if not already present):
```
*.pyc
__pycache__/
db.sqlite3
.env
*.egg-info/
dist/
build/
venv/
.venv/
staticfiles/
media/
```

### Step 11: Create custom User model (if auth needed)

In `apps/core/models.py`:
```python
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Custom user model. Always define at project start."""
    class Meta:
        indexes = []
```

### Step 12: Create root urls.py

Wire up all app URLs with namespacing:
```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Add app URLs as created
]
```

### Step 13: Run initial migration check

```bash
python manage.py check
python manage.py makemigrations
```

Do NOT run `migrate` yet — let the user review first.

## Phase 3: Summary

After generating, present a summary:

1. **What was created** — list of files and directories
2. **Next steps** — what to do first (create venv, install requirements, run migrations)
3. **Key decisions made** — settings structure, auth approach, app layout
4. **Reference** — point to the django-design skill for ongoing guidance

```
Project created successfully!

Next steps:
  1. python -m venv venv && source venv/bin/activate
  2. pip install -r requirements/development.txt
  3. python manage.py migrate
  4. python manage.py createsuperuser
  5. python manage.py runserver
```
