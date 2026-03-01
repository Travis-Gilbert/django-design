---
name: django-design
description: This skill should be used when the user asks to build a Django project, design models or schemas, create views and APIs, configure deployment or settings, set up authentication, customize the admin, optimize performance, configure background tasks, build CMS features, integrate external APIs, create forms or templates, build django-cotton components, add HTMX or Alpine.js interactivity, style with Tailwind CSS, create D3 visualizations, establish a design system, review migrations, or scaffold apps. It covers the full Django stack from database models through production-ready frontend.
version: 3.0.0
---

# Django Design

This skill guides the creation of well-architected Django applications across the full stack: from database models and business logic through templates, components, and interactive frontend. It prevents both backend slop (bloated views, tangled models, missing indexes) and frontend slop (inconsistent styling, scattered interactivity, unmaintainable templates).

## Design Thinking

Before writing any code, understand the shape of the application:

- **Domain**: Identify the real-world process being modeled. Determine the nouns (models) and verbs (actions) in the domain.
- **Scale**: Determine whether this is a small internal tool or a public-facing portal. Scale changes everything from caching to database design.
- **Integration surface**: Identify external systems: databases, APIs, file storage, email services, legacy systems. Each integration point needs its own consideration.
- **Users and roles**: Map who touches the system: admins, staff, public users, API consumers. Define permission boundaries early.
- **Deployment target**: Identify the target: Vercel serverless, traditional VPS, Docker, PaaS. Configuration varies dramatically.
- **Interactivity model**: Determine where interactivity lives. Server-rendered pages enhanced with HTMX? Client-side state with Alpine.js? Data visualization with D3? This shapes template architecture and asset strategy.
- **Component strategy**: Decide early whether to use django-cotton components, plain template includes, or django-material. Mixing component systems creates maintenance nightmares.
- **Design tokens**: Establish semantic color roles, typography scale, and spacing before building templates. A design system prevents visual inconsistency across the project.

Build with these principles:

1. **Fat models, thin views.** Place business logic on models and managers, not in views. Views orchestrate; models compute.
2. **Explicit over clever.** Use Django's conventions. Choose class-based views when they simplify, function-based when they clarify. Never use a pattern just because it exists.
3. **Configuration as layers.** Compose settings cleanly across environments without conditional spaghetti.
4. **Security by default.** Django ships secure. Every `@csrf_exempt`, `allow_all_origins`, or hardcoded secret requires explicit justification.
5. **Test what matters.** Test models and business logic thoroughly. Give template rendering and URL routing smoke tests. Do not test Django itself.
6. **Server-first interactivity.** Start with HTMX for server-driven interactions. Add Alpine.js only for client-side UI state that does not need a server round-trip. Reach for D3 only for complex data visualization.
7. **Semantic design tokens.** Use color roles (`primary`, `error`, `surface`) instead of raw values (`#1e40af`). This enables theme switching and keeps the design consistent.

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
            templatetags/      # shared template tags and filters
                core_tags.py
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
        base.html              # site-wide base template
        base_studio.html       # section base (optional)
        includes/              # shared partials (nav, footer, pagination)
        cotton/                # django-cotton components
            card.html
            button/
                filled.html
                outlined.html
        your_app/
            list.html          # full page templates
            _list_partial.html # HTMX partials (prefixed with underscore)
            detail.html
    static/
        css/
            tokens.css         # design system tokens (colors, typography, spacing)
            main.css           # base styles
        js/
            main.js            # Alpine.js init, shared behavior
            alpine-components.js  # reusable Alpine.data() functions
            charts/            # D3 chart modules
                utils.js       # shared chart setup
    requirements/
        base.txt
        development.txt
        production.txt
```

Key decisions in this structure:

**Settings as a package** rather than a single file. This eliminates `if DEBUG` blocks and environment-sniffing. Each environment file imports from `base.py` and overrides what it needs.

**Apps inside an `apps/` directory** to keep the project root clean. A `core` app holds shared abstractions so other apps don't depend on each other.

**A `services.py` file** for logic that coordinates across multiple models or involves external API calls. This prevents views from becoming business logic dumps.

**Templates organized by app, not by type.** Components go in `templates/cotton/`. HTMX partials are prefixed with underscore (`_list_partial.html`). This keeps related templates together.

**Static assets organized by purpose.** Design tokens in `tokens.css`, Alpine components in their own file, D3 charts in a `charts/` directory. Each has a clear responsibility.

## Reference Library

Each topic has a dedicated reference file with deep patterns, code examples, and anti-patterns. The library is organized into two pillars plus cross-cutting concerns.

### Backend

Core server-side architecture, data layer, and infrastructure.

- **`references/models.md`** - Abstract base models, field selection, index strategy, relationships, N+1 prevention, custom managers, signals, database constraints
- **`references/views.md`** - FBV vs CBV guidance, template-based views, URL patterns, middleware, pagination, file uploads, error handling
- **`references/api.md`** - DRF ViewSets, serializer patterns (list vs detail), router config, permissions, throttling, filtering, pagination, Django Ninja alternatives
- **`references/auth-and-security.md`** - Built-in auth, external providers (Clerk, Auth0), permissions, role-based access, security settings, CORS, rate limiting
- **`references/admin.md`** - Model registration, list_display, filters, fieldsets, custom actions, inline models, django-unfold, admin performance
- **`references/deployment.md`** - Vercel serverless, Gunicorn + Nginx, Docker, environment variables, connection pooling, static files, health checks, logging
- **`references/background-tasks.md`** - Celery, django-rq, Huey, task design (idempotency, retries, timeouts), queue architecture, periodic tasks, monitoring
- **`references/cms-and-content.md`** - Content models, publishable workflows, page trees, placeholder/plugin architecture, content versioning, draft/live patterns

### Frontend

Templates, components, interactivity, and design system.

- **`references/templates.md`** - Base template pattern, template inheritance, custom tags/filters, django-cotton components (definition, slots, props, dynamic attributes, Alpine integration), django-material, context processors
- **`references/forms.md`** - ModelForm patterns, plain forms, formsets, custom widgets, form rendering control, validation order. See also templates.md for form field components
- **`references/htmx.md`** - Core HTMX attributes with Django examples, partial template pattern, CSRF handling, search with debounce, inline editing, infinite scroll, OOB swaps, boosted navigation, django-unicorn alternative
- **`references/alpine.md`** - Core directives (x-data, x-show, x-bind, x-model, x-for), Alpine + HTMX pairing patterns, Alpine + Cotton components, reusable data functions, transitions, passing Django data safely
- **`references/tailwind.md`** - Django integration (django-tailwind and django-tailwind-cli), template usage, JIT and content scanning, responsive patterns, dark mode, component styling, production optimization
- **`references/d3-django.md`** - Data handoff (json_script filter vs API endpoints), bar charts, line charts, force-directed graphs, responsive SVG, D3 + Alpine reactivity, chart file organization
- **`references/design-system.md`** - Semantic color tokens, typography scale, spacing system, component-level tokens, Tailwind config mapping, Material Design 3 integration, light/dark theme switching

### Cross-Cutting

Concerns that span both backend and frontend.

- **`references/performance.md`** - Query optimization, N+1 detection, annotations, only()/defer(), bulk operations, caching (low-level, template fragment, per-view), profiling, EXPLAIN ANALYZE, assertNumQueries
- **`references/testing.md`** - factory_boy, pytest-django, testing business logic, view tests, constraint tests, query count tests, test organization
- **`references/integrations.md`** - Client class pattern, authentication handling, retry with backoff, logging external calls, caching stable data, graceful degradation, testing mocked integrations

### Reading Guide

For tasks that span both pillars, read references from each:

| Task Type | Read |
|-----------|------|
| New list page with filtering | views.md, templates.md, htmx.md |
| API endpoint serving chart data | api.md, d3-django.md, performance.md |
| Form with client-side validation | forms.md, alpine.md, htmx.md |
| Dashboard with data visualizations | views.md, templates.md, d3-django.md, design-system.md |
| Reusable UI component | templates.md (Cotton section), design-system.md, tailwind.md |
| Full CRUD feature | models.md, views.md, forms.md, templates.md, testing.md |

## Agents

Five specialized agents provide targeted review and assistance:

| Agent | Focus | Use When |
|-------|-------|----------|
| `django-architect` | Full architecture review | Starting a new project, major refactoring, cross-pillar design decisions |
| `django-profiler` | Performance analysis | Slow queries, N+1 detection, caching strategy, load testing results |
| `django-migrator` | Migration safety | Schema changes, data migrations, zero-downtime deployments |
| `django-api-reviewer` | API design review | New endpoints, serializer patterns, auth/permissions setup, API versioning |
| `django-frontend` | Frontend integration review | Template structure, HTMX patterns, component conventions, accessibility |

## Anti-Patterns to Avoid

These are the Django equivalent of "AI slop." They look plausible but create real problems:

### Backend
- **God views** that handle GET, POST, validation, business logic, emails, and redirects in one function. Split them.
- **Raw SQL everywhere** when the ORM handles it fine. Use `select_related` and `prefetch_related` before reaching for raw SQL.
- **Settings in views.** Do not import `settings` to check environment. Use feature flags, middleware, or context processors.
- **Signals for business logic.** Signals are for decoupled, optional side effects (clearing a cache, sending analytics). If the logic is essential, call it directly.
- **Circular imports between apps.** If App A imports from App B and vice versa, the app boundaries are wrong. Restructure.
- **Unbounded querysets.** Every list endpoint needs pagination. Every queryset in a loop needs limits.
- **Dangerous migrations.** Dropping columns, renaming fields, and adding non-nullable columns to populated tables all require careful migration strategies. See the django-migrator agent.

### Frontend
- **`{{ data|safe }}` in JavaScript.** Use Django's `json_script` filter for XSS-safe data transfer to Alpine or D3. Never inject unescaped data into script tags.
- **Fat templates with business logic.** If you have `{% if essay.word_count > 3000 and essay.stage == 'drafting' %}`, that logic belongs on the model as a property or method.
- **Hardcoded hex colors in templates.** Use semantic tokens (`bg-primary`, `text-error`) instead of raw values (`bg-[#1e40af]`). Hardcoded colors break theme switching.
- **Mixing component systems.** Pick one component approach (Cotton, django-material, plain templates) and use it consistently. Mixing creates maintenance nightmares.
- **Alpine for server communication.** Use HTMX for server interactions that return HTML. Alpine handles client-side state only.
- **Fixed-size SVG charts.** Always use `viewBox` for responsive D3 charts. Pixel-width SVGs break on mobile.
- **Deep template inheritance.** Three layers (base, section, page) is the limit. Four or more layers make it impossible to trace where a block is defined.
- **Hardcoded URLs in templates.** Use `{% url %}` tags and `reverse()`. Always.
