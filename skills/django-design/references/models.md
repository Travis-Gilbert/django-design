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
    compliance data, financial records). Override the default
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
- `SoftDeleteModel`: When deletion needs to be reversible or auditable. Common in government, healthcare, finance.
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
- `PositiveIntegerField()` when negative values make no sense (quantities, ages).

**Date and time:**
- `DateTimeField()` for moments in time (when something happened).
- `DateField()` for calendar dates without time (birth dates, due dates).
- `DurationField()` for elapsed time between events.
- Always store datetimes in UTC. Use `django.utils.timezone.now()`, never `datetime.now()`.

**Choices and status fields:**
```python
class Status(models.TextChoices):
    PENDING = 'pending', 'Pending Review'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    COMPLETED = 'completed', 'Completed'

status = models.CharField(
    max_length=20,
    choices=Status.choices,
    default=Status.PENDING,
    db_index=True,  # if you filter by status often
)
```

Use `TextChoices` over `IntegerChoices` unless you have a specific reason. String values are self-documenting in the database and in API responses.

**Boolean fields:**
- `BooleanField(default=False)` for flags. Always set a default.
- `BooleanField(null=True)` should be rare. Three-state booleans (True/False/Unknown) are confusing. Consider a status field with choices instead.

**File fields:**
- `FileField(upload_to='documents/%Y/%m/')` organizes uploads by date.
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
class Property(TimeStampedModel):
    parcel_id = models.CharField(max_length=20, unique=True)  # unique implies index
    address = models.CharField(max_length=255, db_index=True)  # simple index
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    program = models.CharField(max_length=50, db_index=True)
    purchase_date = models.DateField(null=True, blank=True)
    buyer = models.ForeignKey('Buyer', on_delete=models.PROTECT)  # auto-indexed
    
    class Meta:
        indexes = [
            # Composite index for the most common query pattern
            models.Index(fields=['program', 'status'], name='idx_program_status'),
            # Partial index for active compliance items only
            models.Index(
                fields=['purchase_date'],
                condition=models.Q(status='active'),
                name='idx_active_purchase_date',
            ),
        ]
        ordering = ['-created_at']
```

**Index rules of thumb:**
- Every `ForeignKey` is auto-indexed. Don't add redundant `db_index=True`.
- Fields in `list_filter` and `search_fields` in admin should be indexed.
- If you write `.filter(field=value)` frequently, index that field.
- Composite indexes serve queries that filter on those fields in order. `Index(fields=['program', 'status'])` helps queries filtering by program alone, or by program AND status, but not by status alone.
- Use partial indexes for queries that only touch a subset of rows (active records, recent items).

## Relationship Patterns

**ForeignKey (many-to-one):**
```python
buyer = models.ForeignKey(
    'Buyer',
    on_delete=models.PROTECT,  # prevent deleting buyers with properties
    related_name='properties',
)
```

Choose `on_delete` carefully:
- `CASCADE`: Child records delete when parent does. Use for data that has no meaning without its parent (order line items, comments on a post).
- `PROTECT`: Prevents deletion of the parent if children exist. Use when the relationship represents real-world ownership (buyer owns properties).
- `SET_NULL`: Sets FK to NULL on parent deletion. Use when the relationship is optional (assigned_to a staff member who leaves). Requires `null=True`.
- `SET_DEFAULT`: Sets FK to a default value. Rare, but useful for reassignment patterns.

**Avoiding N+1 queries:**
```python
# BAD: hits the database once per property
properties = Property.objects.all()
for prop in properties:
    print(prop.buyer.name)  # each access triggers a query

# GOOD: one query with a JOIN
properties = Property.objects.select_related('buyer').all()
for prop in properties:
    print(prop.buyer.name)  # no additional queries

# For reverse relations and M2M, use prefetch_related
buyers = Buyer.objects.prefetch_related('properties').all()
for buyer in buyers:
    for prop in buyer.properties.all():  # no additional queries
        print(prop.address)
```

Use `select_related` for ForeignKey and OneToOneField (follows the JOIN). Use `prefetch_related` for reverse ForeignKey, ManyToManyField, and GenericRelation (executes a separate query, then joins in Python).

## Custom Managers and QuerySets

Managers and querysets are how you encode common queries into reusable, chainable building blocks.

```python
class PropertyQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status='active')
    
    def overdue(self):
        return self.filter(
            purchase_date__lt=timezone.now().date() - timedelta(days=180),
            status__in=['active', 'pending_review'],
        )
    
    def for_program(self, program):
        return self.filter(program=program)
    
    def with_compliance_stats(self):
        """Annotate with computed compliance data."""
        return self.annotate(
            days_owned=ExpressionWrapper(
                Value(timezone.now().date()) - F('purchase_date'),
                output_field=DurationField(),
            ),
            document_count=Count('documents'),
        )


class PropertyManager(models.Manager):
    def get_queryset(self):
        return PropertyQuerySet(self.model, using=self._db)
    
    def active(self):
        return self.get_queryset().active()
    
    def overdue(self):
        return self.get_queryset().overdue()


class Property(TimeStampedModel):
    objects = PropertyManager()
    # ...
```

This lets you chain naturally: `Property.objects.active().for_program('featured_homes').overdue()`

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
# INSTEAD OF a post_save signal to create a compliance record...

class Property(TimeStampedModel):
    @classmethod
    def create_with_compliance(cls, **kwargs):
        """Create a property and its initial compliance record together."""
        property = cls.objects.create(**kwargs)
        ComplianceRecord.objects.create(
            property=property,
            status='pending',
            due_date=property.purchase_date + timedelta(days=180),
        )
        return property
```

Direct calls are debuggable, testable, and visible in the code. Signals are none of those things.

## Database Constraints

Use Django's constraint framework to enforce data integrity at the database level, not just in Python validation.

```python
class Meta:
    constraints = [
        # A property can only be in one active compliance review at a time
        models.UniqueConstraint(
            fields=['property', 'review_type'],
            condition=models.Q(status='active'),
            name='unique_active_review_per_property',
        ),
        # Purchase price must be positive
        models.CheckConstraint(
            check=models.Q(purchase_price__gt=0),
            name='positive_purchase_price',
        ),
        # End date must be after start date
        models.CheckConstraint(
            check=models.Q(end_date__gt=models.F('start_date')),
            name='end_after_start',
        ),
    ]
```

Constraints catch bugs that validation misses (bulk imports, management commands, direct database access, race conditions). Always define them in addition to form/serializer validation, not instead of it.
