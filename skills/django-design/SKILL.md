---
name: django-design
description: Use when the user asks about Django project architecture, project structure, settings organization, app layout, design principles, fat models vs thin views, service layers, cross-app dependencies, environment configuration, or starting a new Django project.
version: 4.0.0
---

# Django Design: Architecture, Structure, and Settings

This skill covers high-level Django project architecture: design thinking, project layout, settings organization, app boundaries, and core principles. For specific implementation domains, see the companion skills below.

## Companion Skills

| Skill | Covers |
|-------|--------|
| `django-backend` | Models, ORM, admin, auth, Celery, CMS |
| `django-api` | DRF, serializers, viewsets, filtering, integrations |
| `django-frontend` | Templates, Cotton, HTMX, Alpine.js, Tailwind, forms, design system |
| `django-ops` | Testing, deployment, performance, security, migrations |
| `django-d3` | D3.js, Observable Plot, data visualization, chart modules |

## Design Thinking

Before writing any code, understand the shape of the application:

- **Domain**: Identify the real-world process being modeled. Determine the nouns (models) and verbs (actions) in the domain.
- **Scale**: Determine whether this is a small internal tool or a public-facing portal. Scale changes everything from caching to database design.
- **Integration surface**: Identify external systems: databases, APIs, file storage, email services, legacy systems. Each integration point needs its own consideration.
- **Users and roles**: Map who touches the system: admins, staff, public users, API consumers. Define permission boundaries early.
- **Deployment target**: Identify the target: Vercel serverless, traditional VPS, Docker, PaaS. Configuration varies dramatically.
- **Interactivity model**: Determine where interactivity lives. Server-rendered pages enhanced with HTMX? Client-side state with Alpine.js? Data visualization with D3? This shapes template architecture and asset strategy.
- **Component strategy**: Decide early whether to use django-cotton components, plain template includes, or another system. Mixing component systems creates maintenance nightmares.
- **Design tokens**: Establish semantic color roles, typography scale, and spacing before building templates. A design system prevents visual inconsistency across the project.

## Core Principles

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
            templatetags/
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

## Anti-Patterns

- **God views** that handle GET, POST, validation, business logic, emails, and redirects in one function. Split them.
- **Settings in views.** Do not import `settings` to check environment. Use feature flags, middleware, or context processors.
- **Circular imports between apps.** If App A imports from App B and vice versa, the app boundaries are wrong. Restructure.
- **Mixing component systems.** Pick one (Cotton, plain templates) and use it consistently.
- **No services layer.** When a view function exceeds 30 lines of business logic, extract to `services.py`.

## Agents

| Agent | Focus |
|-------|-------|
| `django-architect` | Full architecture review, cross-pillar design decisions |
| `django-developer` | General Django development, project scaffolding |
| `fullstack-developer` | Features spanning database through frontend |
| `backend-developer` | Server-side architecture and API design |
| `python-pro` | Advanced Python patterns and type safety |
