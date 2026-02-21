---
name: django-design
description: This skill should be used when the user asks to "build a Django project", "create Django models", "design a Django API", "set up Django settings", "configure Django for deployment", "build a Django admin interface", "integrate Django with external APIs", "scaffold a Django app", "design database schemas for Django", "create Django views and URLs", "create Django forms", or "set up Django middleware". Also trigger when the user mentions Django in combination with words like "project", "app", "model", "view", "API", "deploy", "admin", "auth", "database", or "template". This skill covers project structure, model design, view patterns, URL routing, authentication, API design, admin customization, deployment configuration, and testing. It does NOT cover pure frontend work (use frontend-design for that) unless Django templates are involved.
version: 1.1.0
---

# Django Design

This skill guides the creation of well-architected Django applications that are clean, maintainable, and production-ready. It prevents the backend equivalent of "AI slop": bloated views, tangled models, missing indexes, insecure defaults, and cargo-culted patterns that look right but fall apart under real use.

## Design Thinking

Before writing any code, understand the shape of the application:

- **Domain**: Identify the real-world process being modeled. Determine the nouns (models) and verbs (actions) in the domain.
- **Scale**: Determine whether this is a small internal tool or a public-facing portal. Scale changes everything from caching to database design.
- **Integration surface**: Identify external systems — databases, APIs, file storage, email services, legacy systems. Each integration point needs its own consideration.
- **Users and roles**: Map who touches the system — admins, staff, public users, API consumers. Define permission boundaries early.
- **Deployment target**: Identify the target — Vercel serverless, traditional VPS, Docker, PaaS. Configuration varies dramatically.

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

## Model Design

Read `references/models.md` for comprehensive model patterns including:
- Abstract base models and when to use them
- Field selection guide (the right field for the job)
- Index strategy and query optimization
- Relationship patterns and avoiding N+1 queries
- Model managers and custom querysets
- Signal usage (and when to avoid signals)
- Data integrity through constraints and validators

## Views and URL Patterns

Read `references/views.md` for view architecture including:
- When to use function-based vs class-based views
- DRF viewset and serializer patterns
- URL naming conventions and namespacing
- Middleware patterns
- Request/response lifecycle
- File upload handling
- Pagination strategies

## Authentication, Permissions, and Security

Read `references/auth-and-security.md` for:
- Django's built-in auth vs third-party options
- Permission architecture (model-level, object-level, role-based)
- API authentication (token, session, JWT considerations)
- Security settings checklist
- CORS configuration
- Rate limiting strategies
- Integrating external auth providers (Clerk, Auth0, etc.)

## Admin Customization

Read `references/admin.md` for admin patterns including:
- Model registration and `list_display` configuration
- Filters, search fields, and readonly fields
- Fieldsets for organizing complex forms
- Custom admin actions for batch operations
- Overriding `get_queryset` for annotations and visibility control
- django-unfold integration for modern admin UIs

## Deployment Configuration

Read `references/deployment.md` for deployment patterns including:
- Vercel serverless deployment with Django
- Traditional deployment (Gunicorn + Nginx)
- Docker configuration
- Static file handling (WhiteNoise, S3, CDN)
- Database connection pooling
- Environment variable management
- Health checks and monitoring
- Migration strategies for production

## External API Integration

Read `references/integrations.md` for integration patterns including:
- One client class per external system
- Internal authentication handling
- Retry with backoff for transient failures
- Logging every external call with timing
- Caching for stable data
- Graceful degradation on external failures

## Testing Strategy

Read `references/testing.md` for testing patterns including:
- Prioritizing business logic tests over Django machinery
- Using `factory_boy` for test data instead of fixtures
- `pytest-django` for pytest-style assertions
- Testing model methods, status transitions, and side effects
- Smoke tests for templates and URL routing

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
