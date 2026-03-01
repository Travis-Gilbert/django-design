# django-design

Production-grade Django development toolkit for Claude Code. Provides architecture guidance, interactive scaffolding, proactive code review, migration safety analysis, and performance profiling.

## Components

### Skill: django-design

Activates automatically when working on Django projects. Covers the full Django development lifecycle with a library of deep-reference guides:

**Core Architecture**
- Project structure (settings package, apps directory, fat models / thin views)
- Model design (field types, indexes, managers, constraints)
- View patterns (FBV vs CBV, DRF, pagination, select_related)
- Authentication (built-in, Clerk/Auth0, token-based)

**Frontend and Templates**
- Forms (ModelForm, formsets, custom widgets, form rendering)
- Template architecture (inheritance, custom tags, partial templates)
- Component libraries (django-cotton, django-material)
- Frontend integration (HTMX, Unpoly, SPA-like patterns)
- Admin customization (django-unfold, fieldsets, actions)

**Infrastructure**
- Deployment (Railway, Vercel, Docker, Gunicorn, static files)
- Performance (query optimization, caching, profiling, EXPLAIN ANALYZE)
- Background tasks (Celery, django-rq, Huey, periodic tasks)

**Specialized**
- CMS and content management (page trees, plugins, versioning, django-cms)
- External API integration (client classes, retry, graceful degradation)
- Testing (factory_boy, pytest-django, query performance tests)

Reference files in `skills/django-design/references/` provide deep dives on each topic.

### Commands

#### /django-design

Interactive full-project scaffold. Asks about project name, domain, scale, auth approach, API style, deployment target, and database, then generates a complete Django project with settings split, apps directory, custom User model, requirements, and security pre-configured.

Usage: Type `/django-design` in Claude Code and follow the prompts.

#### /django-app

Scaffold a new app inside an existing project. Detects your project layout, creates the app with proper `apps.py` configuration, wires URLs, registers in `INSTALLED_APPS`, generates models with indexes and constraints, creates admin registrations, and sets up test scaffolding with factory_boy.

Usage: Type `/django-app` in Claude Code and follow the prompts.

#### /django-model

Interactive model generation from domain descriptions. You describe the real-world process ("essays with pipeline stages, field notes, research sources, and shelf entries") and it generates models with proper field types, relationships, indexes, constraints, managers, admin configuration, and test factories.

Usage: Type `/django-model` in Claude Code and follow the prompts.

### Agents

#### django-architect

Architecture reviewer that triggers proactively after writing significant Django code (models, views, settings, admin) and reactively when asked. Checks for missing indexes, N+1 query risks, security issues, fat-view anti-patterns, and more. Fixes Critical and Warning issues automatically.

#### django-migrator

Migration safety reviewer that triggers after running `makemigrations` or writing migration files. Catches dangerous operations before they reach production: dropping columns without backwards compatibility, non-nullable additions to populated tables, RunPython functions that load entire tables into memory, and index operations that lock tables. Fixes Critical issues automatically.

#### django-profiler

Performance profiler invoked when you report a slow endpoint or ask for query optimization. Traces the full request path (URL > view > queryset > serializer/template), counts queries, identifies N+1 patterns, checks index coverage, and provides specific fixes with expected impact. Outputs a detailed query trace table with recommended optimizations ranked by impact.

## Installation

Already installed as a local plugin. To reinstall or share:

1. Copy the `django-design/` directory to `~/.claude/plugins/marketplaces/local-desktop-app-uploads/`
2. Restart Claude Code

## File Structure

```
django-design/
├── .claude-plugin/
│   └── plugin.json
├── commands/
│   ├── django-design.md        # Full project scaffold
│   ├── django-app.md           # App scaffold
│   └── django-model.md         # Model generator
├── agents/
│   ├── django-architect.md     # Architecture reviewer
│   ├── django-migrator.md      # Migration safety
│   └── django-profiler.md      # Performance profiling
└── skills/
    └── django-design/
        ├── SKILL.md
        └── references/
            ├── models.md
            ├── views.md
            ├── auth-and-security.md
            ├── forms-and-templates.md
            ├── admin.md
            ├── deployment.md
            ├── performance.md
            ├── background-tasks.md
            ├── cms-and-content.md
            ├── integrations.md
            └── testing.md
```

## Version History

**v2.0.0** — Added forms-and-templates, performance, background-tasks, and cms-and-content references. Added django-migrator and django-profiler agents. Added /django-app and /django-model commands. Updated skill description and reference library.

**v1.1.0** — Initial release with django-design skill, /django-design command, and django-architect agent.
