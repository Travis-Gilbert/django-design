# Django-Design V4: Claude Code Python/Django Expertise Plugin

> A Claude Code plugin that makes Claude extraordinarily good at Django and the Python web ecosystem by giving it access to real framework source code, specialized agent roles, and curated example patterns.

**Version:** 4.0
**Tech Stack:** Python, Django, DRF, Celery, HTMX, Alpine.js, Cotton, D3, Tailwind CSS

---

## Project Overview

This is a skill directory for Claude Code containing agent definitions, framework source repos, and example code. When Claude Code works inside this directory (or a project that references it), it can grep through the actual source of Django, DRF, Celery, Cotton, and others to understand how things really work -- not how training data remembers them working.

Nothing here executes in production. It is all context for Claude Code.

---

## When to Use Reference Source Code

Do NOT rely on training data for framework internals. Instead:

- **Django ORM questions**: grep through `refs/django-main/django/db/` for the actual implementation. The `models/`, `backends/`, and `sql/` directories contain the real query compilation, field implementations, and migration engine.

- **DRF questions**: check `refs/django-rest-framework-main/rest_framework/` for serializer internals, permission classes, and viewset routing. The actual field validation logic is in `fields.py` and `serializers.py`. Also check `refs/Rest framework/` for additional reference material.

- **Celery questions**: grep `refs/celery-main/celery/` for the actual task execution, canvas primitives (chain, group, chord), and worker internals.

- **Admin questions**: check `refs/django-main/django/contrib/admin/` for the actual ModelAdmin, InlineModelAdmin, and admin site implementations.

- **Cotton component questions**: check `refs/django-cotton-main/` for the component system internals. The `src-loose/` subdirectory has key source files extracted for quick reference: `_component.py` (component rendering), `_slot.py` (slot system), `_vars.py` (variable handling), `cotton_loader.py` (template loader), and `tag_parser.py` (tag compilation).

- **HTMX questions**: two directories to check. `refs/htmx-master/` has the JavaScript library source. `refs/django-htmx-main/` has the Django bridge (middleware, response classes, template helpers).

- **Alpine.js questions**: check `refs/alpine-main/` for source and `refs/Alpine references/` for reference patterns.

- **Template questions**: compare implementations across `refs/django-cotton-main/` (components), `refs/django-htmx-main/` (HTMX integration), and `refs/django-template-partials-main/` (partials) to understand how different libraries solve frontend problems in Django.

- **Alternative API framework questions**: check `refs/Django-Ninja/` for django-ninja's pydantic-based approach. Compare with DRF in `refs/django-rest-framework-main/` to understand the trade-offs.

- **Image handling questions**: check `refs/django-imagekit-develop/` for image processing patterns and `refs/Django image optimizer/` for optimization approaches.

- **Reactive component questions**: check `refs/django-unicorn-main/` for server-rendered reactive components (an alternative to HTMX for some use cases).

- **Tailwind CSS integration**: check `refs/django-tailwind-cli-main/` and `refs/django-tailwind-master/` for different Tailwind integration approaches.

- **D3 / visualization questions**: check `refs/d3-main/` for D3 source, `refs/plot-main/` for Observable Plot, `refs/framework-main/` for Observable Framework. Check `refs/brushable-scatterplot/` for an interactive D3 example. Also check `D3js-code-examples-I-love/` for curated D3 code examples (force graphs, treemaps, circle packing, star maps, voronoi stippling) and `plot-rough/` for an Observable Plot example with rough/sketchy rendering style.

- **Filtering questions**: check `refs/django-filter-main/` for FilterSet patterns. Pairs with DRF for API filtering.

---

## When to Use Agent Definitions

The `agents/` directory contains specialized role definitions. Read the relevant agent .md file before starting work that falls in its domain.

**Key agents by task:**

| Task | Agent File |
|------|-----------|
| Building Django models and queries | `orm-specialist.md` |
| REST API design | `drf-specialist.md` or `api-designer.md` |
| Admin customization | `admin-specialist.md` |
| Templates, HTMX, Cotton, Alpine | `template-specialist.md` |
| Background tasks | `celery-specialist.md` |
| Authentication and permissions | `auth-specialist.md` |
| Writing tests | `testing-specialist.md` |
| Deployment and DevOps | `deployment-engineer.md` |
| Performance and caching | `performance-specialist.md` |
| Security hardening | `security-specialist.md` |
| Data visualization endpoints | `data-specialist.md` |
| Code quality improvements | `refactoring-specialist.md` |
| Full-stack feature work | `fullstack-developer.md` |
| General Django | `django-developer.md` or `backend-developer.md` |
| Build tooling | `build-engineer.md` |
| Advanced Python patterns | `python-pro.md` |
| Framework migrations | `legacy-modernizer.md` or `migration-specialist.md` |
| ML integration | `ml-engineer.md` |

---

## When to Use Example Code

- **HTML references**: check `examples/html-references/` for component, layout, and form patterns with Alpine, HTMX, and Cotton.

- **Template patterns**: check `examples/template-references/` for multiple template organization approaches.

- **Settings patterns**: check `examples/config-references/` for Django settings, pyproject.toml, and app configuration.

- **Content publishing patterns**: check `examples/content-publishing-site/` for the full example domain with two Django services.

- **ORM patterns**: check `examples/orm-patterns/` before writing complex queries.

---

## The Example Domain

All code examples use a content publishing site with two Django services:

- **Publishing API** (apps/content/): Essay, FieldNote, ShelfEntry, Project, VideoProject, and supporting models. Content has stages (research, drafting, production, published) and serializes to markdown for a static site generator.

- **Research API** (apps/research/): Source, SourceLink, ResearchThread, and user-submitted suggestions. Runs as a separate service.

Cross-service references use slug strings, not ForeignKeys. SourceLink uses `content_type` + `content_slug` to bridge services. All examples follow this pattern.

---

## Rules

1. Always verify framework APIs against source code in `refs/` before writing code that depends on them. Training data may be outdated.

2. When writing ORM queries, check `examples/orm-patterns/` first.

3. When designing model fields, check how Django's built-in fields work in `refs/django-main/django/db/models/fields/`.

4. When writing DRF serializers, check how the framework handles nested writes, validation ordering, and field-level vs object-level validation in `refs/django-rest-framework-main/rest_framework/serializers.py`.

5. When building Cotton components, check `refs/django-cotton-main/src-loose/` for the slot system, variable passing, and tag compilation.

6. Cross-reference frameworks when asked to integrate them. Having Django, DRF, Celery, Cotton, and HTMX source side by side is the whole point.

7. Test data in `data/` is available for prototyping.

8. Never use em dashes in any generated code or documentation.

---

## Current Status

| Area | Status | Notes |
|------|--------|-------|
| Directory structure | Done | agents/, refs/, examples/, skills/, data/ all exist |
| Existing agents (9) | Done | api-designer, backend-developer, build-engineer, django-developer, fullstack-developer, legacy-modernizer, ml-engineer, python-pro, refactoring-specialist |
| New agents (13) | Done | orm, drf, admin, template, celery, auth, testing, deployment, performance, security, data, cms, migration specialists |
| Skills (6) | Done | django-design, django-backend, django-api, django-frontend, django-ops, django-d3 with references |
| Core refs (V3.1) | Done | alpine, d3, cotton, DRF, ninja, imagekit, unicorn, tailwind, htmx, plot, framework |
| New refs (V4) | Partial | django-main, celery-main, django-htmx-main, django-filter-main, django-template-partials-main cloned; missing pytest-django, factory-boy, gunicorn, whitenoise, debug-toolbar, pydantic, httpx, django-cachalot, django-lifecycle |
| D3 examples | Done | D3js-code-examples-I-love/ (force graphs, treemaps, circle packing, star maps), plot-rough/ (Observable Plot with rough styling) |
| Example patterns | Not started | orm-patterns, admin-patterns, drf-patterns, celery-patterns, htmx-patterns, testing-patterns, deployment-configs, d3-django |
| Content publishing site | Not started | Full example project |
| Test data | Partial | flare.json exists; need essays-sample, sources-sample, threads-sample, content-graph |
| References docs | Not started | Architecture and decision documents |
| Templates/scaffolds | Not started | Starter scaffolds for common patterns |
| AGENTS.md registry | Exists | May need update for V4 agents |

---

## Next Steps

1. Clone remaining V4 reference repos (pytest-django, factory-boy, gunicorn, whitenoise, debug-toolbar, pydantic, httpx, django-cachalot, django-lifecycle)
2. Update AGENTS.md registry with new agents and routing rules
3. Build example pattern directories
4. Build the content-publishing-site example project
5. Create test data files
6. Write references/ architecture docs
7. Create templates/ starter scaffolds

---

## Recent Decisions

| Decision | Why | Date |
|----------|-----|------|
| V4 upgrade from V3.1 | Add Django source, new agents, better organization, example domain | 2026-03-01 |
| Slug-based cross-service references | Two Django services can not share ForeignKeys; slugs are portable | 2026-03-01 |
| Cotton src-loose directory | Quick grep access to Cotton internals without navigating deep package structure | Pre-V4 |
| Grouped skill split (6 skills) | Monolithic skill (7,450 lines of references) too broad for keyword matching; 6 domain-focused skills enable precise context loading | 2026-03-02 |
| D3 code examples as top-level dirs | Curated D3 examples and plot-rough kept as standalone reference directories alongside refs/ | 2026-03-02 |

---

## Development Commands

```bash
# Clone a missing reference repo
git clone https://github.com/<org>/<repo>.git refs/<repo-name>/

# Check what refs are present
ls refs/

# Check agent coverage
ls agents/

# Verify Cotton source files
ls refs/django-cotton-main/src-loose/
```
