---
name: django-design
description: This skill should be used when the user asks to build a Django project, design Django models or database schemas, create views and APIs, configure deployment or settings, set up authentication and permissions, customize the Django admin, optimize query performance, configure background tasks with Celery or django-rq, build CMS or content management features, integrate external APIs, create Django forms or templates, integrate HTMX or Unpoly, review Django migrations, or scaffold a new Django app. It covers the full Django backend lifecycle from project structure through production deployment. It does NOT cover pure frontend work (use frontend-design for that) unless Django templates are involved.
version: 2.0.0
---

# Django Design

This skill guides the creation of well-architected Django applications that are clean, maintainable, and production-ready. It prevents the backend equivalent of "AI slop": bloated views, tangled models, missing indexes, insecure defaults, and cargo-culted patterns that look right but fall apart under real use.

## Design Thinking

Before writing any code, understand the shape of the application:

- **Domain**: Identify the real-world process being modeled. Determine the nouns (models) and verbs (actions) in the domain.
- **Scale**: Determine whether this is a small internal tool or a public-facing portal. Scale changes everything from caching to database design.
- **Integration surface**: Identify external systems: databases, APIs, file storage, email services, legacy systems. Each integration point needs its own consideration.
- **Users and roles**: Map who touches the system: admins, staff, public users, API consumers. Define permission boundaries early.
- **Deployment target**: Identify the target: Vercel serverless, traditional VPS, Docker, PaaS. Configuration varies dramatically.

Build with these principles:

1. **Fat models, thin views.** Place business logic on models and managers, not in views. Views orchestrate; models compute.
2. **Explicit over clever.** Use Django's conventions. Choose class-based views when they simplify, function-based when they clarify. Never use a pattern just because it exists.
3. **Configuration as layers.** Compose settings cleanly across environments without conditional spaghetti.
4. **Security by default.** Django ships secure. Every `@csrf_exempt`, `allow_all_origins`, or hardcoded secret requires explicit justification.
5. **Test what matters.** Test models and business logic thoroughly. Give template rendering and URL routing smoke tests. Do not test Django itself.

## Project Structure

For new projects, use this structure. It scales from a single-app tool to a multi-app platform without reorganization.

```
project_name/
    manage.py
    project_name/
        __init__.py
        settings/
            __init__.py        # imports from base, detects environment
            base.py            # shared settings
            development.py     # local overrides
            production.py      # production overrides
            test.py            # test-specific (fast passwords, in-memory cache)
        urls.py                # root URL conf, includes app URLs
        wsgi.py
        asgi.py
    apps/
        core/                  # shared utilities, base models, middleware
            models.py          # abstract base models (TimeStampedModel, etc.)
            middleware.py
            utils.py
        your_app/
            models.py
            views.py
            urls.py
            admin.py
            forms.py           # if using Django forms/templates
            serializers.py     # if using DRF
            services.py        # complex business logic that spans models
            tests/
                __init__.py
                test_models.py
                test_views.py
    templates/
        base.html
        your_app/
    static/
        css/
        js/
    requirements/
        base.txt
        development.txt
        production.txt
```

Key decisions in this structure:

**Settings as a package** rather than a single file. This eliminates `if DEBUG` blocks and environment-sniffing. Each environment file imports from `base.py` and overrides what it needs. The `__init__.py` detects the environment via `DJANGO_SETTINGS_MODULE` or a simple env var check.

**Apps inside an `apps/` directory** to keep the project root clean. Add `apps/` to the Python path in settings or use relative imports. A `core` app holds shared abstractions so other apps don't depend on each other.

**A `services.py` file** for logic that coordinates across multiple models or involves external API calls. This prevents views from becoming business logic dumps and keeps models focused on data behavior.

**Split requirements files** because production does not need `django-debug-toolbar` and development does not need `gunicorn`.

## Reference Library

Each topic has a dedicated reference file with deep patterns, code examples, and anti-patterns:

### Core Architecture
- **`references/models.md`** — Abstract base models, field selection, index strategy, relationships, N+1 prevention, custom managers, signals, database constraints
- **`references/views.md`** — FBV vs CBV, DRF viewsets, serializer patterns, URL conventions, middleware, pagination, file uploads, error handling
- **`references/auth-and-security.md`** — Built-in auth, external providers (Clerk, Auth0), permissions, role-based access, security settings, CORS, rate limiting, input validation

### Frontend and Templates
- **`references/forms-and-templates.md`** — ModelForm patterns, formsets, custom widgets, template inheritance, django-cotton components, django-material integration, HTMX patterns, Unpoly integration
- **`references/admin.md`** — Model registration, list_display, filters, fieldsets, custom actions, inline models, django-unfold, admin performance

### Infrastructure
- **`references/deployment.md`** — Vercel serverless, Gunicorn + Nginx, Docker, environment variables, connection pooling, static files, health checks, migration strategies, logging
- **`references/performance.md`** — Query optimization, N+1 detection, annotations, only()/defer(), bulk operations, raw SQL, caching (low-level, template fragment, per-view), profiling, EXPLAIN ANALYZE, assertNumQueries, index maintenance
- **`references/background-tasks.md`** — Celery, django-rq, Huey, task design (idempotency, serialization, retries, timeouts), queue architecture, periodic tasks, management commands, testing async work, monitoring

### Specialized
- **`references/cms-and-content.md`** — Flat content models, publishable workflows, page trees (treebeard, mptt), placeholder/plugin architecture, content versioning, draft/live patterns, django-cms integration
- **`references/integrations.md`** — Client class pattern, authentication handling, retry with backoff, logging external calls, caching stable data, graceful degradation, testing mocked integrations
- **`references/testing.md`** — factory_boy, pytest-django, testing business logic, view tests, constraint tests, query count tests, test organization

## Anti-Patterns to Avoid

These are the Django equivalent of "AI slop." They look plausible but create real problems:

- **God views** that handle GET, POST, validation, business logic, emails, and redirects in one function. Split them.
- **Raw SQL everywhere** when the ORM handles it fine. Use `select_related` and `prefetch_related` before reaching for raw SQL.
- **Settings in views.** Do not import `settings` to check environment. Use feature flags, middleware, or context processors.
- **Signals for business logic.** Signals are for decoupled, optional side effects (clearing a cache, sending analytics). If the logic is essential, call it directly.
- **Circular imports between apps.** If App A imports from App B and vice versa, the app boundaries are wrong. Restructure.
- **`@csrf_exempt` on every view** because the frontend cannot handle CSRF. Fix the frontend instead.
- **Hardcoded URLs in templates.** Use `{% url %}` tags and `reverse()`. Always.
- **Model methods that hit the database multiple times.** If a method runs 5 queries every call, it belongs in an annotation or a prefetch.
- **Unbounded querysets.** Every list endpoint needs pagination. Every queryset in a loop needs limits.
- **Dangerous migrations.** Dropping columns, renaming fields, and adding non-nullable columns to populated tables all require careful migration strategies. See the django-migrator agent.
