---
description: Generate Django models from a domain description with proper fields, indexes, constraints, and managers
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
argument-hint: (interactive — no arguments needed)
---

# Django Model Generator

Guide the user through creating well-designed Django models from a domain description. This command translates real-world processes into database models with proper field types, relationships, indexes, constraints, managers, and admin configuration.

## Phase 1: Understand the Domain

### Step 1: Detect the Project

```bash
# Find existing models to understand naming conventions and base classes
find . -name "models.py" -not -path "*/venv/*" | head -20
grep -r "TimeStampedModel\|AbstractUser\|SoftDeleteModel" . --include="models.py" -l | head -10

# Find existing apps
find . -name "apps.py" -not -path "*/venv/*" | head -20

# Check for core base models
cat apps/core/models.py 2>/dev/null || echo "No core models found"
```

### Step 2: Gather Requirements

Use AskUserQuestion to ask in 1-2 batches:

**Batch 1: Domain Description**

1. **Target app** — Which app should these models live in? List existing apps and let the user choose or create a new one.
2. **Domain description** — Describe the real-world process these models represent. Be specific about the nouns (entities), their attributes, and how they relate to each other. (e.g., "Property inspections where an inspector visits a property, takes photos, checks items on a checklist, and submits a pass/fail report that gets reviewed by a manager")
3. **Key workflows** — What are the main things users do with this data? (e.g., "Create inspections, assign inspectors, upload photos, approve/reject reports")

**Batch 2: Technical Details** (based on domain analysis)

4. **Proposed models** — Based on the domain, suggest models with their key fields and relationships. Ask the user to confirm or adjust. Be specific about field types.
5. **Special requirements** — Ask about:
   - Soft delete needed? (audit trails, compliance data)
   - Status workflows? (draft > review > approved > archived)
   - File uploads? (images, documents)
   - External system integration? (IDs from other systems)
   - Multi-tenancy? (data scoped to organizations)

## Phase 2: Design the Models

Before writing code, plan the model architecture:

### Relationship Mapping

For each relationship identified:

- **One-to-many**: ForeignKey on the "many" side
  - Choose `on_delete` carefully: CASCADE, PROTECT, SET_NULL
  - Set `related_name` explicitly (never rely on Django's default `<model>_set`)
- **Many-to-many**: ManyToManyField, or explicit through table if the relationship has attributes
- **One-to-one**: OneToOneField for extending existing models (user profiles, settings)

### Field Type Selection

Apply these rules:

| Data Type | Field | Notes |
|-----------|-------|-------|
| Names, titles, codes | `CharField(max_length=N)` | Set realistic max_length |
| Long text, descriptions | `TextField()` | Never CharField(max_length=9999) |
| Money, currency | `DecimalField(max_digits=12, decimal_places=2)` | Never FloatField |
| Counts, quantities | `PositiveIntegerField()` | Use BigInteger if > 2.1B |
| Yes/no flags | `BooleanField(default=False)` | Always set default |
| Status, category | `CharField` with `TextChoices` | Add db_index=True |
| Dates (calendar) | `DateField()` | For due dates, birthdays |
| Dates (moments) | `DateTimeField()` | For timestamps, events |
| Email addresses | `EmailField()` | Built-in validation |
| URLs | `URLField()` | Built-in validation |
| Files | `FileField(upload_to='...')` | Organize by date |
| Images | `ImageField(upload_to='...')` | Adds image validation |
| External IDs | `CharField(max_length=100, db_index=True)` | Index for lookups |
| UUIDs | `UUIDField(default=uuid.uuid4)` | For public-facing IDs |

### Index Strategy

Add indexes for:
- Every field used in `.filter()` that is not already a ForeignKey or unique
- Fields used in `list_filter` and `search_fields` in admin
- Composite indexes for common multi-field queries
- Partial indexes for queries that only touch a subset of rows

### Constraint Planning

Add constraints for:
- Business rules that must be enforced at the database level
- Uniqueness rules that span multiple fields
- Value ranges (prices > 0, dates in order)

## Phase 3: Generate Code

### Step 1: Write models.py

Generate the complete models.py file with:

```python
# Standard library imports
import uuid
from datetime import timedelta
from decimal import Decimal

# Django imports
from django.conf import settings
from django.db import models
from django.utils import timezone

# Project imports
from apps.core.models import TimeStampedModel  # if available


class <Status>Choices(models.TextChoices):
    """Choices for <Model>.status field."""
    DRAFT = 'draft', 'Draft'
    # ... appropriate choices for the domain


class <Model>QuerySet(models.QuerySet):
    """Reusable query filters for <Model>."""

    def active(self):
        return self.filter(status=<Status>Choices.ACTIVE)

    # ... additional common filters based on domain


class <Model>Manager(models.Manager):
    def get_queryset(self):
        return <Model>QuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()


class <Model>(<BaseClass>):
    """<Docstring explaining what this model represents in the domain.>"""

    # Fields grouped logically:
    # 1. Core identity fields
    # 2. Domain-specific fields
    # 3. Relationship fields
    # 4. Status and workflow fields
    # 5. Metadata fields (if not inherited)

    objects = <Model>Manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=[...], name='idx_<descriptive_name>'),
        ]
        constraints = [
            models.UniqueConstraint(fields=[...], name='unique_<description>'),
            models.CheckConstraint(check=models.Q(...), name='check_<description>'),
        ]
        verbose_name = '<Human Readable>'
        verbose_name_plural = '<Human Readable Plural>'

    def __str__(self):
        return self.<most_descriptive_field>

    # Business logic methods
    # Properties for computed values
    # Class methods for creation patterns
```

### Step 2: Write admin.py

Generate admin registrations for every model:

```python
from django.contrib import admin
from .models import <Model>


@admin.register(<Model>)
class <Model>Admin(admin.ModelAdmin):
    list_display = [...]        # 4-6 useful columns
    list_filter = [...]         # filterable fields (must be indexed)
    search_fields = [...]       # searchable text fields
    readonly_fields = [...]     # timestamps, computed fields
    list_select_related = [...] # ForeignKey fields shown in list_display
    date_hierarchy = '...'      # if there's a primary date field

    fieldsets = [
        ('<Section Name>', {'fields': [...]}),
        ('Metadata', {'fields': [...], 'classes': ['collapse']}),
    ]
```

### Step 3: Write factories.py

Generate factory_boy factories for testing:

```python
import factory
from .models import <Model>


class <Model>Factory(factory.django.DjangoModelFactory):
    class Meta:
        model = <Model>

    # Use appropriate Faker providers
    # Use SubFactory for ForeignKeys
    # Use Sequence for unique fields
    # Use LazyAttribute for computed defaults
```

### Step 4: Generate Initial Serializers (if DRF app)

```python
from rest_framework import serializers
from .models import <Model>


class <Model>ListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoints."""
    class Meta:
        model = <Model>
        fields = [...]  # only what the list view needs


class <Model>DetailSerializer(serializers.ModelSerializer):
    """Full serializer for detail/create/update endpoints."""
    class Meta:
        model = <Model>
        fields = [...]
        read_only_fields = ['id', 'created_at', 'updated_at']
```

### Step 5: Generate Migration

```bash
python manage.py makemigrations <app_name>
python manage.py showmigrations <app_name>
python manage.py check
```

Do NOT run `migrate`. Let the user review first.

## Phase 4: Review and Validate

After generating, present a summary:

### Model Summary Table

```
| Model | Fields | Relationships | Indexes | Constraints |
|-------|--------|---------------|---------|-------------|
| Inspection | 8 | property (FK), inspector (FK) | status, date | unique active per property |
| ChecklistItem | 5 | inspection (FK) | position | positive score |
| InspectionPhoto | 4 | inspection (FK), item (FK) | - | - |
```

### Relationship Diagram

```
Property ←──── Inspection ────→ Inspector (User)
                   │
                   ├── ChecklistItem
                   │
                   └── InspectionPhoto
```

### Generated Files

```
Created:
  apps/<app>/models.py        — <N> models with managers, constraints
  apps/<app>/admin.py         — Admin registrations
  apps/<app>/tests/factories.py — factory_boy factories

Migration ready:
  python manage.py migrate <app>
```

### Design Decisions

Explain the key design choices:
- Why certain on_delete values were chosen
- Why specific indexes were added
- Why constraints enforce certain business rules
- Any trade-offs made (e.g., denormalization for query performance)
