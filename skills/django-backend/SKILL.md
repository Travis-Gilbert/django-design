---
name: django-backend
description: Use when the user asks about Django models, ORM queries, querysets, managers, migrations, database optimization, admin customization, ModelAdmin, inlines, authentication, permissions, user models, social auth, Celery tasks, background jobs, task queues, beat scheduling, CMS features, or content management workflows.
version: 4.0.0
---

# Django Backend: Models, Admin, Auth, Tasks, and Content

This skill covers Django's server-side data layer: models and ORM, admin customization, authentication and permissions, background tasks with Celery, and content management patterns.

## Reference Library

- **`references/models.md`** -- Abstract base models, field selection, index strategy, relationships, N+1 prevention, custom managers, signals, database constraints
- **`references/admin.md`** -- Model registration, list_display, filters, fieldsets, custom actions, inline models, django-unfold, admin performance
- **`references/auth-and-security.md`** -- Built-in auth, external providers (Clerk, Auth0), permissions, role-based access, security settings, CORS, rate limiting
- **`references/background-tasks.md`** -- Celery, django-rq, Huey, task design (idempotency, retries, timeouts), queue architecture, periodic tasks, monitoring
- **`references/cms-and-content.md`** -- Content models, publishable workflows, page trees, placeholder/plugin architecture, content versioning, draft/live patterns

## Quick Guidance

### Models and ORM

- Start with a `TimeStampedModel` abstract base. Nearly every table needs `created_at` and `updated_at`.
- Use `select_related` for ForeignKey/OneToOne joins, `prefetch_related` for reverse FKs and M2M.
- Add `db_index=True` to fields you filter or order by frequently.
- Use `UniqueConstraint` and `CheckConstraint` over legacy `unique_together`.
- Move complex query logic into custom managers and querysets, not views.

### Admin

- Always set `list_display`, `list_filter`, and `search_fields`. Default admin is usable; configured admin is powerful.
- Use `readonly_fields` for computed values. Use `fieldsets` to group related fields.
- Override `get_queryset()` to add `select_related`/`prefetch_related` for admin performance.

### Auth and Permissions

- Always use a custom user model, even if identical to the default -- you cannot change this later.
- Use Django's permission system for object-level access. Avoid custom boolean fields like `is_editor`.
- For external auth (Clerk, Auth0), keep Django's `User` model as the local reference.

### Celery

- Tasks must be idempotent. Calling the same task twice with the same arguments should produce the same result.
- Use `bind=True` for self-referencing tasks (retry, logging).
- Set `acks_late=True` and `reject_on_worker_lost=True` for critical tasks.
- Never pass Django model instances to tasks. Pass primary keys and re-fetch inside the task.

## Anti-Patterns

- **God views** that handle GET, POST, validation, business logic, emails, and redirects in one function. Split them.
- **Raw SQL everywhere** when the ORM handles it fine. Use `select_related` and `prefetch_related` before reaching for raw SQL.
- **Signals for business logic.** Signals are for decoupled, optional side effects (clearing a cache, sending analytics). If the logic is essential, call it directly.
- **Circular imports between apps.** If App A imports from App B and vice versa, the app boundaries are wrong. Restructure.
- **Unbounded querysets.** Every list endpoint needs pagination. Every queryset in a loop needs limits.

## Agents

| Agent | Focus |
|-------|-------|
| `orm-specialist` | Deep ORM queries, custom fields, migration strategies |
| `admin-specialist` | Admin customization, inlines, actions, custom views |
| `auth-specialist` | Authentication flows, permissions, social auth, JWT |
| `celery-specialist` | Task design, canvas primitives, beat scheduling, workers |
| `cms-specialist` | Content modeling, workflows, headless CMS patterns |
