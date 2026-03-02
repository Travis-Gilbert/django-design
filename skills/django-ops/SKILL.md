---
name: django-ops
description: Use when the user asks about Django testing, pytest, factory_boy, test fixtures, deployment, Docker, Gunicorn, CI/CD, static files, performance optimization, query profiling, N+1 queries, caching, database indexing, security hardening, OWASP, CSP headers, CORS, migrations, or Django version upgrades.
version: 4.0.0
---

# Django Ops: Testing, Deployment, Performance, and Security

This skill covers operational concerns for Django applications: test strategy and tooling, deployment configurations, performance optimization, security hardening, and migration management.

## Reference Library

- **`references/testing.md`** -- factory_boy, pytest-django, testing business logic, view tests, constraint tests, query count tests, test organization
- **`references/deployment.md`** -- Vercel serverless, Gunicorn + Nginx, Docker, environment variables, connection pooling, static files, health checks, logging
- **`references/performance.md`** -- Query optimization, N+1 detection, annotations, only()/defer(), bulk operations, caching (low-level, template fragment, per-view), profiling, EXPLAIN ANALYZE, assertNumQueries

## Quick Guidance

### Testing

- Use pytest-django over Django's built-in test runner. Fixtures, parametrize, and plugins make tests more expressive.
- Use factory_boy for test data. Factories replace fixtures and make tests self-documenting.
- Test business logic thoroughly. Give views and URLs smoke tests. Do not test Django itself.
- Use `assertNumQueries` to catch N+1 regressions early.
- Organize tests by module: `test_models.py`, `test_views.py`, `test_services.py`.

### Deployment

- Use Gunicorn with `--workers` based on CPU count (2*cores + 1 is the starting formula).
- Collect static files with `collectstatic`. Use WhiteNoise for self-hosted static serving.
- Set `ALLOWED_HOSTS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` in production settings.
- Use connection pooling (pgbouncer or django-db-connection-pool) for PostgreSQL under load.
- Add health check endpoints for load balancer probes.

### Performance

- Most Django performance problems are database problems. Profile queries first.
- Use `select_related` for FK joins, `prefetch_related` for reverse relations and M2M.
- Use `only()` and `defer()` to limit fields when you do not need the full model.
- Use `bulk_create()` and `bulk_update()` for batch operations instead of loops.
- Cache stable data: per-view with `@cache_page`, per-fragment with `{% cache %}`, per-object with Django's low-level cache.
- Use `EXPLAIN ANALYZE` in PostgreSQL to understand actual query plans.

### Security

- Django ships secure by default. The most dangerous thing is disabling protections without understanding them.
- Never use `@csrf_exempt` without a documented reason. Use `csrf_protect` on sensitive views.
- Set security headers: `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS`, `SECURE_HSTS_SECONDS`.
- Validate all user input. Use Django forms or DRF serializers -- never trust raw `request.POST`.
- Store secrets in environment variables, never in settings files or version control.
- Audit `CORS_ALLOWED_ORIGINS`. Never use `CORS_ALLOW_ALL_ORIGINS=True` in production.

### Migrations

- Test migrations on a copy of production data before deploying.
- For zero-downtime deployments: add columns as nullable first, backfill, then add constraints.
- Never rename fields in a single migration on a live database. Use add-copy-drop over multiple deployments.
- Use `RunSQL` with reverse SQL for data migrations that need to be rollback-safe.

## Anti-Patterns

- **No test data factories.** Creating test data manually in each test leads to brittle, verbose tests.
- **Testing Django internals.** Do not test that `Model.save()` calls the database. Test your business logic.
- **DEBUG=True in production.** This exposes stack traces, database queries, and settings to attackers.
- **No query profiling.** If you have not run `assertNumQueries` or django-debug-toolbar, you have N+1 problems.
- **Dangerous migrations.** Dropping columns, renaming fields, and adding non-nullable columns to populated tables all require careful strategies.

## Agents

| Agent | Focus |
|-------|-------|
| `testing-specialist` | pytest-django, factory_boy, test architecture, fixtures |
| `deployment-engineer` | Gunicorn, Docker, CI/CD, static files, monitoring |
| `performance-specialist` | Query profiling, N+1, caching, indexing, load testing |
| `security-specialist` | OWASP, CSP, CORS, secrets management, security headers |
| `migration-specialist` | Django/Python upgrades, dependency migration, modernization |
| `django-migrator` | Migration safety review, zero-downtime deployment |
| `django-profiler` | Performance analysis, slow query detection |
