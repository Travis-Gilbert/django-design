"""
ORM Pattern: Custom Migration Operations
==========================================

Demonstrates custom migration patterns for Django projects. Covers
RunPython with forward and reverse functions, data migrations for
backfilling fields, and adding indexes concurrently on PostgreSQL.

These patterns go in actual migration files (e.g., 0005_backfill_slugs.py).
They are shown here as standalone examples for reference.

All examples use the content publishing domain (Essay, Tag, FieldNote).
"""

from django.db import migrations, models


# ---------------------------------------------------------------------------
# Pattern 1: RunPython with Forward and Reverse Functions
# ---------------------------------------------------------------------------

def populate_reading_time(apps, schema_editor):
    """
    Forward function: compute reading_time_minutes from word_count.

    Uses apps.get_model() to get the historical model version, which
    only has the fields that exist at this point in the migration history.
    Do NOT import the model directly -- that would use the current model
    definition which may have fields that do not exist yet.
    """
    Essay = apps.get_model("content", "Essay")

    essays = Essay.objects.filter(reading_time_minutes=0, word_count__gt=0)
    updated = []

    for essay in essays.iterator(chunk_size=1000):
        essay.reading_time_minutes = max(1, essay.word_count // 250)
        updated.append(essay)

        # Batch updates to avoid memory issues on large tables
        if len(updated) >= 1000:
            Essay.objects.bulk_update(updated, ["reading_time_minutes"])
            updated = []

    if updated:
        Essay.objects.bulk_update(updated, ["reading_time_minutes"])


def reverse_reading_time(apps, schema_editor):
    """
    Reverse function: reset reading_time_minutes to zero.

    Every RunPython should have a reverse function so the migration can
    be rolled back. If the operation is truly irreversible, use
    migrations.RunPython.noop as the reverse, but document why.
    """
    Essay = apps.get_model("content", "Essay")
    Essay.objects.all().update(reading_time_minutes=0)


class Migration0005(migrations.Migration):
    """
    Example migration: Backfill reading_time_minutes from word_count.

    In a real project, this class would be named Migration and live in
    a file like content/migrations/0005_backfill_reading_time.py.
    """

    dependencies = [
        ("content", "0004_essay_reading_time_minutes"),
    ]

    operations = [
        migrations.RunPython(
            populate_reading_time,
            reverse_reading_time,
            hints={"model_name": "essay"},
        ),
    ]


# ---------------------------------------------------------------------------
# Pattern 2: Data Migration for Backfilling a New Field
# ---------------------------------------------------------------------------

def backfill_essay_slugs(apps, schema_editor):
    """
    Generate slugs for existing essays that were created before the slug
    field was added.

    Handles slug uniqueness by appending a counter. Uses iterator() and
    batch saves to handle large datasets without loading everything into
    memory at once.
    """
    from django.utils.text import slugify

    Essay = apps.get_model("content", "Essay")

    essays_without_slugs = Essay.objects.filter(
        models.Q(slug="") | models.Q(slug__isnull=True)
    )

    existing_slugs = set(
        Essay.objects.exclude(slug="")
        .exclude(slug__isnull=True)
        .values_list("slug", flat=True)
    )

    updated = []
    for essay in essays_without_slugs.iterator(chunk_size=500):
        base_slug = slugify(essay.title)

        if not base_slug:
            base_slug = f"essay-{essay.pk}"

        slug = base_slug
        counter = 1
        while slug in existing_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1

        essay.slug = slug
        existing_slugs.add(slug)
        updated.append(essay)

        if len(updated) >= 500:
            Essay.objects.bulk_update(updated, ["slug"])
            updated = []

    if updated:
        Essay.objects.bulk_update(updated, ["slug"])


def reverse_backfill_slugs(apps, schema_editor):
    """
    Reverse: clear all slugs. This is destructive but allows rollback.
    In practice, you may want RunPython.noop if slugs should persist.
    """
    Essay = apps.get_model("content", "Essay")
    Essay.objects.all().update(slug="")


class Migration0008(migrations.Migration):
    """
    Example migration: Backfill slugs for existing essays.
    """

    dependencies = [
        ("content", "0007_essay_slug"),
    ]

    operations = [
        migrations.RunPython(
            backfill_essay_slugs,
            reverse_backfill_slugs,
            hints={"model_name": "essay"},
        ),
        # After backfilling, add the unique constraint.
        # This order matters: data first, then constraint.
        migrations.AlterField(
            model_name="essay",
            name="slug",
            field=models.SlugField(max_length=255, unique=True),
        ),
    ]


# ---------------------------------------------------------------------------
# Pattern 3: Adding an Index Concurrently (PostgreSQL)
# ---------------------------------------------------------------------------

class Migration0012(migrations.Migration):
    """
    Add an index concurrently on PostgreSQL.

    CONCURRENTLY avoids locking the table during index creation, which is
    critical for large tables in production. Without it, the entire table
    is locked for writes during the index build.

    Requirements:
    - PostgreSQL only (SQLite and MySQL do not support CONCURRENTLY)
    - atomic = False on the migration class (PostgreSQL cannot run
      CREATE INDEX CONCURRENTLY inside a transaction)
    - The migration must be run manually or in a deployment step that
      allows non-atomic migrations
    """

    # CRITICAL: Must be False for CONCURRENTLY to work.
    # Django normally wraps each migration in a transaction.
    atomic = False

    dependencies = [
        ("content", "0011_previous_migration"),
    ]

    operations = [
        # AddIndex with a partial index and CONCURRENTLY
        migrations.AddIndex(
            model_name="essay",
            index=models.Index(
                fields=["stage", "-published_at"],
                name="essay_pub_listing_conc",
                condition=models.Q(stage="published"),
            ),
        ),
        # For the CONCURRENTLY keyword, use SeparateDatabaseAndState
        # or a RunSQL operation:
    ]


class Migration0013(migrations.Migration):
    """
    Alternative: Use RunSQL for full control over index creation.

    SeparateDatabaseAndState lets you:
    1. Run raw SQL for the actual database change
    2. Tell Django's state tracker what the schema looks like afterward

    This is the most reliable way to create indexes concurrently because
    you have complete control over the SQL.
    """

    atomic = False

    dependencies = [
        ("content", "0012_add_index_concurrently"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                        "essay_author_stage_idx "
                        "ON content_essay (author_id, stage, published_at DESC) "
                        "WHERE stage = 'published'"
                    ),
                    reverse_sql=(
                        "DROP INDEX CONCURRENTLY IF EXISTS essay_author_stage_idx"
                    ),
                ),
            ],
            state_operations=[
                migrations.AddIndex(
                    model_name="essay",
                    index=models.Index(
                        fields=["author", "stage", "-published_at"],
                        name="essay_author_stage_idx",
                        condition=models.Q(stage="published"),
                    ),
                ),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Pattern 4: Safe Column Addition with Defaults
# ---------------------------------------------------------------------------

class Migration0015(migrations.Migration):
    """
    Safe pattern for adding a column with a default on large tables.

    On PostgreSQL 11+, adding a column with a default is fast because
    the default is stored in the catalog, not written to every row.

    On older PostgreSQL or other databases, adding a column with a default
    rewrites the entire table. In that case, split it into three steps:
    1. Add the nullable column (instant)
    2. Backfill the default value in batches (data migration)
    3. Set NOT NULL and default (alter column)
    """

    dependencies = [
        ("content", "0014_previous_migration"),
    ]

    operations = [
        # Step 1: Add nullable column (fast, no table rewrite)
        migrations.AddField(
            model_name="essay",
            name="content_format",
            field=models.CharField(
                max_length=20,
                null=True,
                blank=True,
                help_text="Content format: markdown, html, or restructuredtext",
            ),
        ),
    ]


def backfill_content_format(apps, schema_editor):
    """
    Step 2: Backfill the default value in batches.
    Runs as a separate migration after the AddField.
    """
    Essay = apps.get_model("content", "Essay")

    # Process in batches to avoid long-running transactions
    batch_size = 5000
    while True:
        # Use a subquery to limit the update to a batch
        batch_ids = list(
            Essay.objects
            .filter(content_format__isnull=True)
            .values_list("id", flat=True)[:batch_size]
        )
        if not batch_ids:
            break

        Essay.objects.filter(id__in=batch_ids).update(content_format="markdown")


class Migration0016(migrations.Migration):
    """Step 2: Backfill content_format in batches."""

    dependencies = [
        ("content", "0015_essay_content_format_nullable"),
    ]

    operations = [
        migrations.RunPython(
            backfill_content_format,
            migrations.RunPython.noop,  # Reverse is noop; field will be dropped if rolled back further
        ),
    ]


class Migration0017(migrations.Migration):
    """
    Step 3: Set the default and make the column non-nullable.
    Only run this after confirming the backfill completed successfully.
    """

    dependencies = [
        ("content", "0016_backfill_content_format"),
    ]

    operations = [
        migrations.AlterField(
            model_name="essay",
            name="content_format",
            field=models.CharField(
                max_length=20,
                default="markdown",
                help_text="Content format: markdown, html, or restructuredtext",
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Pattern 5: Renaming a Field Safely
# ---------------------------------------------------------------------------

class Migration0020(migrations.Migration):
    """
    Rename a field safely.

    Django's RenameField handles both the database column rename and the
    Python field name change in one operation. On PostgreSQL, this is a
    fast metadata-only operation (ALTER TABLE RENAME COLUMN).

    Caution: Code that references the old field name will break.
    Coordinate the migration with code changes in the same deployment.
    """

    dependencies = [
        ("content", "0019_previous_migration"),
    ]

    operations = [
        migrations.RenameField(
            model_name="essay",
            old_name="body",
            new_name="content_body",
        ),
    ]


# ---------------------------------------------------------------------------
# Notes on Migration Best Practices
# ---------------------------------------------------------------------------

"""
Migration best practices for production deployments:

1. ALWAYS provide a reverse function for RunPython operations.
   Use RunPython.noop only when the reverse truly has no effect.

2. Use iterator() and batch processing for data migrations on large tables.
   Loading millions of rows into memory will crash the migration.

3. Set atomic = False when using CREATE INDEX CONCURRENTLY on PostgreSQL.
   Concurrent index creation cannot run inside a transaction.

4. Split schema and data changes into separate migrations:
   - Migration N: AddField (nullable)
   - Migration N+1: RunPython (backfill data)
   - Migration N+2: AlterField (set default, remove null)

5. Test migrations both forward and backward:
   python manage.py migrate content 0008  # Forward
   python manage.py migrate content 0007  # Backward

6. Use squashmigrations to consolidate old migrations:
   python manage.py squashmigrations content 0001 0020

7. Never edit a migration that has already been applied in production.
   Create a new migration instead.

8. Use --check in CI to catch missing migrations:
   python manage.py makemigrations --check --dry-run

9. For zero-downtime deployments, ensure migrations are backward-compatible:
   - Adding a column: nullable first, then backfill, then constrain
   - Removing a column: remove code references first, then drop in a later deploy
   - Renaming: add new column, backfill, update code, drop old column
"""
