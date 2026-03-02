# Django Performance Reference

## Query Optimization

Most Django performance problems are database problems. The ORM makes it easy to write queries that look like one database call but generate dozens. Understanding what the ORM does under the hood is the single most impactful performance skill for Django developers.

### Identifying N+1 Queries

The N+1 problem: you fetch N objects, then for each object you access a related object, triggering N additional queries.

```python
# BAD: 1 query for essays + N queries for authors
essays = Essay.objects.all()
for essay in essays:
    print(essay.created_by.username)  # each .created_by triggers a SELECT

# GOOD: 1 query with JOIN
essays = Essay.objects.select_related('created_by').all()
for essay in essays:
    print(essay.created_by.username)  # no additional queries

# GOOD: For reverse FKs and M2M, use prefetch_related
projects = VideoProject.objects.prefetch_related('scenes').all()
for project in projects:
    for scene in project.scenes.all():  # pre-fetched, no extra queries
        print(scene.title)
```

**When to use which:**
- `select_related`: ForeignKey and OneToOneField. Performs a SQL JOIN, returns results in a single query.
- `prefetch_related`: Reverse ForeignKey, ManyToManyField, GenericRelation. Runs a separate query per relationship, then joins in Python. Also works with `Prefetch` objects for filtered or annotated prefetches.

```python
from django.db.models import Prefetch

# Prefetch with filtering: only narration scenes
projects = VideoProject.objects.prefetch_related(
    Prefetch(
        'scenes',
        queryset=VideoScene.objects.filter(scene_type='narration').order_by('order'),
        to_attr='narration_scenes',
    )
)
for project in projects:
    for scene in project.narration_scenes:  # no extra queries, already filtered
        print(scene.script_text)
```

### Annotations vs Python Computation

Move computation to the database when you can. SQL is faster than Python for aggregation.

```python
from django.db.models import Count, Avg, Sum, F, Q, Value, ExpressionWrapper, DurationField
from django.utils import timezone

# BAD: Computing in Python
projects = VideoProject.objects.all()
for project in projects:
    scene_count = project.scenes.count()  # N queries
    days = (timezone.now().date() - project.created_at.date()).days  # fine, but can't sort/filter

# GOOD: Annotate in SQL
projects = VideoProject.objects.annotate(
    scene_count=Count('scenes'),
    total_duration=Sum('scenes__estimated_seconds'),
).filter(
    scene_count__gt=0,  # can now filter on computed values
).order_by('-total_duration')  # and sort by them
```

### only() and defer()

These limit which columns are fetched. Useful when models have large text or binary fields that you do not need for a particular query.

```python
# Fetch only the fields needed for a list view
essays = Essay.objects.only('id', 'title', 'stage', 'date')

# Defer the heavy body and thesis fields
essays = Essay.objects.defer('body', 'thesis')
```

**Use sparingly.** Accessing a deferred field triggers a new query per object. Only use when you are certain the deferred fields will not be accessed. The cost of an accidental deferred field access is worse than fetching the full row.

### Bulk Operations

```python
from django.utils.text import slugify

# BAD: N individual INSERT statements
for title in title_list:
    Essay.objects.create(title=title, slug=slugify(title), stage='drafting')

# GOOD: Single bulk INSERT
essays = [
    Essay(title=title, slug=slugify(title), stage='drafting')
    for title in title_list
]
Essay.objects.bulk_create(essays, batch_size=500)

# GOOD: Bulk UPDATE
Essay.objects.filter(stage='drafting', draft=True).update(stage='research')

# GOOD: Bulk UPDATE with per-object values (Django 4.2+)
essays = Essay.objects.filter(stage='production')
for essay in essays:
    essay.stage = 'published'
    essay.draft = False
Essay.objects.bulk_update(essays, ['stage', 'draft'], batch_size=500)
```

**bulk_create caveats:** Signals are not fired. `auto_now` / `auto_now_add` fields work, but custom `save()` logic is skipped. If your model's `save()` does important work, you need to handle it separately.

### Raw SQL

The ORM handles the vast majority of queries. Reach for raw SQL only when the ORM cannot express what you need, or when a complex query is significantly faster as raw SQL.

```python
# Use .raw() for queries that return model instances
projects = VideoProject.objects.raw('''
    SELECT p.*, COUNT(s.id) as scene_count
    FROM content_videoproject p
    LEFT JOIN content_videoscene s ON s.project_id = p.id
    WHERE p.phase = %s
    GROUP BY p.id
    HAVING COUNT(s.id) < %s
''', ['production', 3])

# Use connection.cursor() for non-model queries
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute('''
        SELECT stage, COUNT(*), AVG(word_count)
        FROM content_essay
        WHERE draft = %s
        GROUP BY stage
    ''', [False])
    results = cursor.fetchall()
```

**Always use parameterized queries.** Never use f-strings or `.format()` to build SQL. Parameterized queries prevent SQL injection.

## Caching

### Cache Framework Setup

```python
# settings/development.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# settings/production.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'KEY_PREFIX': 'content',
        'TIMEOUT': 300,  # 5 minutes default
    }
}
```

### Low-Level Cache API

```python
from django.core.cache import cache


def get_pipeline_stats():
    """Cache expensive pipeline computation for 5 minutes."""
    cache_key = 'pipeline:stats'
    stats = cache.get(cache_key)
    if stats is not None:
        return stats

    stats = {
        'total_essays': Essay.objects.count(),
        'published': Essay.objects.filter(stage='published').count(),
        'stale_drafts': Essay.objects.stale_drafts().count(),
        'avg_word_count': Essay.objects.filter(stage='published').aggregate(
            avg=Avg('word_count')
        )['avg'],
    }
    cache.set(cache_key, stats, timeout=300)
    return stats


def invalidate_pipeline_cache():
    """Call this when essay data changes."""
    cache.delete('pipeline:stats')
```

### Template Fragment Caching

Cache expensive template sections without caching the entire page.

```html
{% load cache %}

{# Cache the sidebar stats for 5 minutes #}
{% cache 300 sidebar_stats request.user.id %}
    <div class="sidebar-stats">
        <p>Published: {{ stats.published }}</p>
        <p>Stale drafts: {{ stats.stale_drafts }}</p>
    </div>
{% endcache %}
```

**Include the user ID (or role, or any varying key) in the cache key** when the content differs per user. Without it, User A sees User B's cached data.

### Per-View Caching

```python
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator


# Function-based view
@cache_page(60 * 5)  # 5 minutes
def public_essay_list(request):
    ...


# Class-based view
@method_decorator(cache_page(60 * 5), name='dispatch')
class PublicEssayListView(ListView):
    ...
```

**Cache public pages, not authenticated pages.** Per-view caching uses the full URL as the cache key. For authenticated views, you risk serving one user's page to another. Use template fragment caching or the low-level API instead.

### Cache Invalidation Patterns

```python
# Signal-based invalidation (acceptable since caching is a side effect)
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver([post_save, post_delete], sender=Essay)
def invalidate_essay_caches(sender, instance, **kwargs):
    cache.delete('pipeline:stats')
    cache.delete(f'essay:{instance.pk}')
    cache.delete_many([
        f'essay_list:stage:{instance.stage}',
        'essay_list:all',
    ])


# Versioned cache keys for bulk invalidation
def get_essay_cache_version():
    version = cache.get('essay:version')
    if version is None:
        version = 1
        cache.set('essay:version', version)
    return version


def bump_essay_cache_version():
    """Increment the version to invalidate all essay caches at once."""
    try:
        cache.incr('essay:version')
    except ValueError:
        cache.set('essay:version', 1)
```

## Profiling and Debugging

### django-debug-toolbar

The single most important development tool for Django performance.

```python
# requirements/development.txt
django-debug-toolbar

# settings/development.py
INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
INTERNAL_IPS = ['127.0.0.1']

# If using Docker, add the Docker gateway IP
import socket
hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
INTERNAL_IPS += [ip[: ip.rfind(".")] + ".1" for ip in ips]
```

**What to look for in the toolbar:**
- **SQL panel**: Total query count and time. If a page runs more than 10 queries, investigate. If any single query takes more than 50ms, optimize it.
- **Duplicate queries**: The toolbar highlights repeated identical queries. These are almost always N+1 problems.
- **Template panel**: How many templates were rendered and which ones. Excessive template includes can slow rendering.
- **Cache panel**: Cache hits vs misses. A high miss rate means your cache strategy is not working.

### EXPLAIN ANALYZE

When a query is slow, ask the database why.

```python
from django.db import connection


def explain_query(queryset):
    """Print the EXPLAIN ANALYZE output for a queryset."""
    sql, params = queryset.query.sql_with_params()
    with connection.cursor() as cursor:
        cursor.execute(f'EXPLAIN ANALYZE {sql}', params)
        for row in cursor.fetchall():
            print(row[0])


# Usage
explain_query(
    Essay.objects.filter(stage='published', draft=False)
)
```

**What to look for:**
- **Seq Scan** on large tables: Missing index. The database is reading every row.
- **Nested Loop** with high row counts: Possible N+1 at the SQL level. Consider a JOIN or subquery.
- **Sort** with high cost: Missing index on the ORDER BY field, or sorting a large result set.
- **Hash Join** vs **Merge Join**: Hash joins are fine for moderate datasets. If you see them on very large joins, check if an index would enable a merge join.

### assertNumQueries

Lock down query counts in tests so regressions are caught immediately.

```python
class TestEssayListPerformance(TestCase):
    def setUp(self):
        for _ in range(50):
            EssayFactory()

    def test_list_view_query_count(self):
        """The list view should use a bounded number of queries
        regardless of how many essays exist."""
        self.client.force_login(self.staff_user)
        with self.assertNumQueries(4):
            # Expected: 1 session + 1 user + 1 count + 1 essays w/ joins
            response = self.client.get(reverse('content:essay-list'))
            self.assertEqual(response.status_code, 200)
```

### Logging Slow Queries

```python
# settings/base.py
LOGGING = {
    'version': 1,
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',  # logs all SQL queries
            'handlers': ['console'],
        },
    },
}

# For production, log only slow queries
# settings/production.py
DATABASE_QUERY_LOG_THRESHOLD = 0.5  # seconds

# apps/core/middleware.py
import time
import logging
from django.db import connection

logger = logging.getLogger('django.db.backends')


class SlowQueryLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        for query in connection.queries:
            duration = float(query['time'])
            if duration > 0.5:
                logger.warning(
                    'Slow query (%.2fs): %s',
                    duration, query['sql'][:500],
                )
        return response
```

## Database Tuning

### Connection Management

```python
# Traditional deployment: reuse connections
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'CONN_MAX_AGE': 600,  # keep connections alive for 10 minutes
        # ...
    }
}

# Serverless (Vercel, Lambda): no persistent connections
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=0,  # close after each request
    )
}
```

### Index Maintenance

Indexes speed up reads but slow down writes. Audit your indexes periodically.

```sql
-- PostgreSQL: find unused indexes
SELECT
    schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexname NOT LIKE '%_pkey'
ORDER BY pg_relation_size(indexrelid) DESC;

-- PostgreSQL: find missing indexes (tables with lots of sequential scans)
SELECT
    relname, seq_scan, seq_tup_read,
    idx_scan, idx_tup_fetch
FROM pg_stat_user_tables
WHERE seq_scan > 100
ORDER BY seq_tup_read DESC;
```

### Pagination for Large Tables

Offset-based pagination (`LIMIT 25 OFFSET 10000`) is slow on large tables because the database still reads and discards the first 10,000 rows. Use cursor-based (keyset) pagination instead.

```python
# Cursor-based pagination using a unique, indexed column
def get_next_page(last_id=None, page_size=25):
    qs = Essay.objects.order_by('id')
    if last_id:
        qs = qs.filter(id__gt=last_id)
    return qs[:page_size]
```

DRF's `CursorPagination` implements this pattern automatically.

## Performance Checklist

Before deploying any view to production, verify:

1. **Query count**: Is it bounded? Does it grow with data volume?
2. **select_related / prefetch_related**: Are all ForeignKey and reverse FK accesses covered?
3. **Pagination**: Is the queryset bounded? No unbounded `.all()` in responses.
4. **Indexes**: Are filtered and sorted fields indexed?
5. **Caching**: Are expensive computations cached? Is the cache invalidated correctly?
6. **Bulk operations**: Are loops of `.save()` replaced with `bulk_create` / `bulk_update` / `.update()`?
7. **Template efficiency**: Are expensive computations happening in the template instead of the view or model?
