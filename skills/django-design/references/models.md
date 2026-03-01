# Django Model Design Reference

## Abstract Base Models

Start every project with a `TimeStampedModel`. Nearly every table benefits from knowing when records were created and last modified.

```python
# apps/core/models.py
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base providing created_at and updated_at fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """Abstract base adding soft-delete capability.

    Use when records should never truly disappear (audit trails,
    published content, research data). Override the default
    manager to exclude deleted records from normal queries.
    """
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    objects = SoftDeleteManager()  # filters out deleted by default
    all_objects = models.Manager()  # includes deleted records

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=['deleted_at', 'updated_at'])

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=['deleted_at', 'updated_at'])

    @property
    def is_deleted(self):
        return self.deleted_at is not None


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)
```

**When to use abstract bases:**
- `TimeStampedModel`: Almost always. The only exception is join tables that Django auto-creates for M2M relationships.
- `SoftDeleteModel`: When deletion needs to be reversible or auditable. Common in publishing, research, and content platforms.
- Custom abstract bases: When 3+ models share the same set of fields. If only 2 models share fields, just duplicate them. Premature abstraction costs more than a little repetition.

## Field Selection Guide

Choosing the right field type matters more than it seems. Here are the decisions that trip people up:

**Text fields:**
- `CharField(max_length=N)` for data with a known maximum (names, codes, statuses). Always set a reasonable `max_length`.
- `TextField()` for unbounded text (descriptions, notes, free-form input). No max_length needed.
- Never use `CharField(max_length=9999)` as a substitute for `TextField`. They generate different column types.

**Numeric fields:**
- `DecimalField(max_digits=M, decimal_places=N)` for money, measurements, or anything where floating-point imprecision matters. Always use Decimal for currency.
- `FloatField()` only for scientific data where approximate precision is acceptable.
- `IntegerField()` / `BigIntegerField()` for counts, IDs, whole numbers. Use `BigInteger` if values might exceed 2.1 billion.
- `PositiveIntegerField()` when negative values make no sense (quantities, word counts).

**Date and time:**
- `DateTimeField()` for moments in time (when something happened).
- `DateField()` for calendar dates without time (publication dates, deadlines).
- `DurationField()` for elapsed time between events.
- Always store datetimes in UTC. Use `django.utils.timezone.now()`, never `datetime.now()`.

**Choices and status fields:**
```python
class Stage(models.TextChoices):
    RESEARCH = 'research', 'Research'
    DRAFTING = 'drafting', 'Drafting'
    PRODUCTION = 'production', 'Production'
    PUBLISHED = 'published', 'Published'

stage = models.CharField(
    max_length=20,
    choices=Stage.choices,
    default=Stage.RESEARCH,
    db_index=True,  # if you filter by stage often
)
```

Use `TextChoices` over `IntegerChoices` unless you have a specific reason. String values are self-documenting in the database and in API responses.

**Boolean fields:**
- `BooleanField(default=False)` for flags. Always set a default.
- `BooleanField(null=True)` should be rare. Three-state booleans (True/False/Unknown) are confusing. Consider a status field with choices instead.

**File fields:**
- `FileField(upload_to='media/%Y/%m/')` organizes uploads by date.
- `ImageField()` adds image validation on top of FileField.
- For production, always use external storage (S3, GCS) via `django-storages`. Never serve user uploads from the Django process.

**UUIDs:**
```python
import uuid

class MyModel(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
```
Use UUID primary keys when: IDs appear in URLs and you don't want sequential guessing, records sync between systems, or you need to generate IDs before saving. The downside is slightly slower joins and larger indexes compared to auto-incrementing integers.

## Index Strategy

Indexes speed up reads at the cost of slightly slower writes. For most Django applications, the read-to-write ratio makes indexes a clear win for any field you filter or sort by.

```python
class Essay(TimeStampedModel):
    slug = models.SlugField(max_length=300, unique=True)  # unique implies index
    title = models.CharField(max_length=300, db_index=True)  # simple index
    stage = models.CharField(max_length=20, choices=Stage.choices, db_index=True)
    date = models.DateField(null=True, blank=True)
    draft = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True)

    class Meta:
        indexes = [
            # Composite index for the most common query pattern
            models.Index(fields=['stage', 'draft'], name='idx_stage_draft'),
            # Partial index for published content only
            models.Index(
                fields=['date'],
                condition=models.Q(stage='published'),
                name='idx_published_date',
            ),
        ]
        ordering = ['-date']
```

**Index rules of thumb:**
- Every `ForeignKey` is auto-indexed. Don't add redundant `db_index=True`.
- Fields in `list_filter` and `search_fields` in admin should be indexed.
- If you write `.filter(field=value)` frequently, index that field.
- Composite indexes serve queries that filter on those fields in order. `Index(fields=['stage', 'draft'])` helps queries filtering by stage alone, or by stage AND draft, but not by draft alone.
- Use partial indexes for queries that only touch a subset of rows (published records, non-draft items).

## Relationship Patterns

**ForeignKey (many-to-one):**
```python
video_scene = models.ForeignKey(
    'VideoProject',
    on_delete=models.CASCADE,  # scenes have no meaning without their video
    related_name='scenes',
)
```

Choose `on_delete` carefully:
- `CASCADE`: Child records delete when parent does. Use for data that has no meaning without its parent (video scenes, thread entries).
- `PROTECT`: Prevents deletion of the parent if children exist. Use when the relationship is important to preserve (essays linked to research threads).
- `SET_NULL`: Sets FK to NULL on parent deletion. Use when the relationship is optional (assigned_to a staff member who leaves). Requires `null=True`.
- `SET_DEFAULT`: Sets FK to a default value. Rare, but useful for reassignment patterns.

**Cross-service references by slug:**
When two Django services reference each other, use slug strings instead of ForeignKeys. This keeps services independently deployable.

```python
class SourceLink(TimeStampedModel):
    """Bridges the Research API to content in the Publishing API."""
    source = models.ForeignKey('Source', on_delete=models.CASCADE, related_name='links')
    content_type = models.CharField(max_length=50)  # 'essay' or 'field_note'
    content_slug = models.SlugField(max_length=300)
    content_title = models.CharField(max_length=300)
    role = models.CharField(max_length=30, choices=LinkRole.choices)
    key_quote = models.TextField(blank=True)
    date_linked = models.DateField(auto_now_add=True)
```

**Avoiding N+1 queries:**
```python
# BAD: hits the database once per essay
essays = Essay.objects.all()
for essay in essays:
    print(essay.video_project.title)  # each access triggers a query

# GOOD: one query with a JOIN
essays = Essay.objects.select_related('video_project').all()
for essay in essays:
    print(essay.video_project.title)  # no additional queries

# For reverse relations and M2M, use prefetch_related
videos = VideoProject.objects.prefetch_related('linked_essays').all()
for video in videos:
    for essay in video.linked_essays.all():  # no additional queries
        print(essay.title)
```

Use `select_related` for ForeignKey and OneToOneField (follows the JOIN). Use `prefetch_related` for reverse ForeignKey, ManyToManyField, and GenericRelation (executes a separate query, then joins in Python).

## Custom Managers and QuerySets

Managers and querysets are how you encode common queries into reusable, chainable building blocks.

```python
class EssayQuerySet(models.QuerySet):
    def published(self):
        return self.filter(stage='published', draft=False)

    def in_progress(self):
        return self.filter(
            stage__in=['research', 'drafting', 'production'],
            draft=True,
        )

    def by_tag(self, tag):
        return self.filter(tags__contains=[tag])

    def with_source_stats(self):
        """Annotate with computed source data."""
        return self.annotate(
            source_count=models.Count(
                'sources', filter=models.Q(sources__isnull=False)
            ),
            word_count=models.functions.Length('body'),
        )


class EssayManager(models.Manager):
    def get_queryset(self):
        return EssayQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()

    def in_progress(self):
        return self.get_queryset().in_progress()


class Essay(TimeStampedModel):
    objects = EssayManager()
    # ...
```

This lets you chain naturally: `Essay.objects.published().by_tag('design').with_source_stats()`

## Signals: Use Sparingly

Signals should be reserved for truly decoupled, optional side effects. If the system would break without the signal firing, it shouldn't be a signal.

**Good uses for signals:**
- Clearing a cache when a model changes
- Sending analytics events
- Creating a log entry in a separate system

**Bad uses for signals (do these directly instead):**
- Creating related records that are required for the parent to function
- Sending notification emails that are part of the business flow
- Updating computed fields on other models

```python
# INSTEAD OF a post_save signal to create a research thread...

class Essay(TimeStampedModel):
    @classmethod
    def create_with_thread(cls, **kwargs):
        """Create an essay and its initial research thread together."""
        essay = cls.objects.create(**kwargs)
        ResearchThread.objects.create(
            title=f'Research: {essay.title}',
            resulting_essay_slug=essay.slug,
            status='active',
            started_date=timezone.now().date(),
        )
        return essay
```

Direct calls are debuggable, testable, and visible in the code. Signals are none of those things.

## Database Constraints

Use Django's constraint framework to enforce data integrity at the database level, not just in Python validation.

```python
class Meta:
    constraints = [
        # A source can only be linked to a given essay once per role
        models.UniqueConstraint(
            fields=['source', 'content_slug', 'role'],
            name='unique_source_link_per_role',
        ),
        # Word count must be positive when set
        models.CheckConstraint(
            check=models.Q(script_word_count__gte=0),
            name='non_negative_word_count',
        ),
        # End date must be after start date
        models.CheckConstraint(
            check=models.Q(ended_at__gt=models.F('started_at')),
            name='end_after_start',
        ),
    ]
```

Constraints catch bugs that validation misses (bulk imports, management commands, direct database access, race conditions). Always define them in addition to form/serializer validation, not instead of it.

## JSON Fields for Flexible Data

Use `JSONField` when the data structure varies per record or is managed as a unit rather than queried relationally.

```python
class Essay(TimeStampedModel):
    # Structured metadata that varies per essay
    sources = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {title, url} objects',
    )
    annotations = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {paragraph, text} margin notes',
    )
    # Per-instance visual overrides for the frontend
    composition = models.JSONField(
        default=dict,
        blank=True,
        help_text='Visual layout overrides: colors, typography, spacing',
    )
```

**When to use JSONField vs relational tables:**
- JSONField: Data is read/written as a unit, not queried individually. Examples: tag lists, composition settings, source references.
- Relational table: You need to filter, join, or aggregate on the nested data. Example: SourceLink (needs queries like "find all sources linked to essays about design").
- In PostgreSQL, JSONField supports `__contains`, `__has_key`, and GIN indexes for efficient lookups.
