"""
Model Testing Patterns
======================

Tests for the Essay and Tag models in the content publishing site.

Patterns demonstrated:
    - @pytest.mark.django_db for database access
    - Testing field defaults and model creation
    - Testing custom model methods
    - Testing model constraints (unique_together, CheckConstraint)
    - Testing custom manager and queryset methods
    - Testing signal behavior
    - @pytest.mark.parametrize for data-driven tests
    - Negative tests (asserting that invalid data raises errors)

Conventions:
    - Test names follow: test_<unit>_<scenario>_<expected_outcome>
    - One assertion per test when practical
    - Fixtures over inline setup
"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.content.models import Essay, Tag

from .factories import EssayFactory, TagFactory, UserFactory


# ===========================================================================
# Model creation and field defaults
# ===========================================================================


@pytest.mark.django_db
class TestEssayCreation:
    """Tests for creating Essay instances and verifying field defaults."""

    def test_create_essay_with_required_fields(self, author):
        """An essay can be created with just a title, slug, and author."""
        essay = Essay.objects.create(
            title="Testing in Django",
            slug="testing-in-django",
            author=author,
        )
        assert essay.pk is not None
        assert essay.title == "Testing in Django"

    def test_default_stage_is_draft(self, essay):
        """New essays default to 'draft' stage."""
        assert essay.stage == "draft"

    def test_published_at_is_none_for_draft(self, essay):
        """Draft essays have no published_at timestamp."""
        assert essay.published_at is None

    def test_created_at_is_auto_set(self, author):
        """created_at is set automatically on first save."""
        essay = Essay.objects.create(
            title="Auto Timestamp",
            slug="auto-timestamp",
            author=author,
        )
        assert essay.created_at is not None
        # Verify it was set to roughly 'now'.
        delta = timezone.now() - essay.created_at
        assert delta.total_seconds() < 5

    def test_factory_produces_valid_essay(self, essay):
        """Sanity check: the factory creates a valid, saved instance."""
        essay.full_clean()  # Runs model validation
        assert essay.pk is not None
        assert essay.author is not None


@pytest.mark.django_db
class TestTagCreation:
    """Tests for Tag model."""

    def test_create_tag(self, db):
        tag = Tag.objects.create(name="python", slug="python")
        assert tag.pk is not None

    def test_tag_str_returns_name(self):
        """Tag.__str__ should return the tag name."""
        tag = TagFactory.build(name="django")
        assert str(tag) == "django"


# ===========================================================================
# Custom model methods
# ===========================================================================


@pytest.mark.django_db
class TestEssayMethods:
    """Tests for custom methods on the Essay model."""

    def test_publish_sets_stage_and_timestamp(self, essay):
        """essay.publish() transitions stage and sets published_at."""
        assert essay.stage == "draft"
        essay.publish()
        essay.refresh_from_db()

        assert essay.stage == "published"
        assert essay.published_at is not None

    def test_publish_is_idempotent(self, published_essay):
        """Calling publish() on an already-published essay is a no-op."""
        original_date = published_essay.published_at
        published_essay.publish()
        published_essay.refresh_from_db()

        assert published_essay.published_at == original_date

    def test_archive_sets_stage(self, published_essay):
        """archive() moves a published essay to archived stage."""
        published_essay.archive()
        published_essay.refresh_from_db()
        assert published_essay.stage == "archived"

    def test_word_count_calculated_on_save(self, author):
        """word_count is recomputed whenever the essay is saved."""
        essay = EssayFactory(author=author, body="one two three four five")
        assert essay.word_count == 5

        essay.body = "one two three"
        essay.save()
        essay.refresh_from_db()
        assert essay.word_count == 3

    def test_reading_time_minutes(self, author):
        """reading_time returns estimated minutes based on word count."""
        # Average reading speed is ~200 words per minute.
        body = " ".join(["word"] * 600)
        essay = EssayFactory(author=author, body=body)
        assert essay.reading_time == 3

    def test_is_published_property(self, essay, published_essay):
        """is_published returns True only for published essays."""
        assert essay.is_published is False
        assert published_essay.is_published is True

    def test_str_returns_title(self, essay):
        """Essay.__str__ should return the title."""
        assert str(essay) == essay.title


# ===========================================================================
# Model constraints
# ===========================================================================


@pytest.mark.django_db
class TestEssayConstraints:
    """Tests for database-level constraints on the Essay model."""

    def test_slug_is_unique(self, author):
        """Two essays cannot share the same slug."""
        EssayFactory(author=author, slug="unique-slug")
        with pytest.raises(IntegrityError):
            EssayFactory(author=author, slug="unique-slug")

    def test_title_cannot_be_blank(self, author):
        """title is required at the model validation level."""
        essay = Essay(title="", slug="no-title", author=author)
        with pytest.raises(ValidationError) as exc_info:
            essay.full_clean()
        assert "title" in exc_info.value.message_dict

    def test_stage_must_be_valid_choice(self, author):
        """stage field only accepts defined choices."""
        essay = Essay(
            title="Bad Stage",
            slug="bad-stage",
            author=author,
            stage="nonexistent",
        )
        with pytest.raises(ValidationError) as exc_info:
            essay.full_clean()
        assert "stage" in exc_info.value.message_dict

    def test_check_constraint_word_count_non_negative(self, author):
        """
        CheckConstraint prevents negative word_count at the DB level.

        This test demonstrates testing a CheckConstraint defined in
        Meta.constraints. The constraint name should match what is
        in the model's Meta class.
        """
        essay = EssayFactory(author=author)
        essay.word_count = -1
        with pytest.raises(IntegrityError):
            essay.save()


# ===========================================================================
# Custom manager and queryset methods
# ===========================================================================


@pytest.mark.django_db
class TestEssayQuerySet:
    """Tests for custom queryset methods on Essay.objects."""

    def test_published_returns_only_published_essays(self, author):
        """The .published() queryset filter returns only published essays."""
        EssayFactory(author=author, stage="draft")
        EssayFactory(author=author, stage="published")
        EssayFactory(author=author, stage="archived")

        result = Essay.objects.published()
        assert result.count() == 1
        assert result.first().stage == "published"

    def test_drafts_returns_only_draft_essays(self, author):
        """The .drafts() queryset filter returns only drafts."""
        EssayFactory(author=author, stage="draft")
        EssayFactory(author=author, stage="published")

        result = Essay.objects.drafts()
        assert result.count() == 1
        assert result.first().stage == "draft"

    def test_by_author_filters_correctly(self, author, user):
        """The .by_author() filter returns essays for a specific author."""
        EssayFactory(author=author)
        EssayFactory(author=author)
        EssayFactory(author=user)  # Different author

        result = Essay.objects.by_author(author)
        assert result.count() == 2

    def test_with_tag_filters_by_tag_name(self, essay_with_tags):
        """The .with_tag() filter returns essays that have a given tag."""
        result = Essay.objects.with_tag("python")
        assert essay_with_tags in result

    def test_recent_orders_by_created_at_descending(self, author):
        """The .recent() method returns essays newest first."""
        old = EssayFactory(author=author)
        new = EssayFactory(author=author)

        result = list(Essay.objects.recent())
        assert result.index(new) < result.index(old)


# ===========================================================================
# Signal behavior
# ===========================================================================


@pytest.mark.django_db
class TestEssaySignals:
    """Tests for Django signals connected to the Essay model."""

    def test_slug_auto_generated_on_save_if_blank(self, author):
        """
        A pre_save signal generates a slug from the title when slug
        is left blank.
        """
        essay = Essay.objects.create(
            title="Auto Slug Test",
            slug="",
            author=author,
        )
        essay.refresh_from_db()
        assert essay.slug == "auto-slug-test"

    def test_post_save_updates_author_essay_count(self, author):
        """
        A post_save signal on Essay increments the author's cached
        essay_count field.
        """
        initial_count = author.profile.essay_count if hasattr(author, "profile") else 0
        EssayFactory(author=author)

        author.refresh_from_db()
        if hasattr(author, "profile"):
            author.profile.refresh_from_db()
            assert author.profile.essay_count == initial_count + 1


# ===========================================================================
# Parametrize: data-driven tests
# ===========================================================================


@pytest.mark.django_db
@pytest.mark.parametrize(
    "stage,is_visible",
    [
        ("draft", False),
        ("published", True),
        ("archived", False),
    ],
    ids=["draft-hidden", "published-visible", "archived-hidden"],
)
def test_essay_visibility_by_stage(author, stage, is_visible):
    """
    Only published essays are visible to the public.

    @pytest.mark.parametrize runs this test three times, once for each
    (stage, is_visible) pair. The 'ids' parameter gives each run a
    readable name in the test output.
    """
    essay = EssayFactory(author=author, stage=stage)
    assert essay.is_visible == is_visible


@pytest.mark.django_db
@pytest.mark.parametrize(
    "title,expected_slug",
    [
        ("Hello World", "hello-world"),
        ("Django & DRF", "django-drf"),
        ("  Extra   Spaces  ", "extra-spaces"),
        ("UPPERCASE TITLE", "uppercase-title"),
    ],
)
def test_slug_generation_from_title(author, title, expected_slug):
    """Slug generation handles various title formats correctly."""
    essay = Essay.objects.create(title=title, slug="", author=author)
    essay.refresh_from_db()
    assert essay.slug == expected_slug


# ===========================================================================
# Edge cases and negative tests
# ===========================================================================


@pytest.mark.django_db
class TestEssayEdgeCases:
    """Edge case and boundary tests."""

    def test_empty_body_has_zero_word_count(self, author):
        essay = EssayFactory(author=author, body="")
        assert essay.word_count == 0

    def test_very_long_title_is_truncated_in_slug(self, author):
        """Slugs longer than 80 chars are truncated."""
        long_title = "a " * 100  # 200 chars worth of title
        essay = EssayFactory(author=author, title=long_title)
        assert len(essay.slug) <= 80

    def test_delete_author_cascades_to_essays(self, author, essay):
        """Deleting an author removes their essays (CASCADE)."""
        essay_pk = essay.pk
        author.delete()
        assert not Essay.objects.filter(pk=essay_pk).exists()

    def test_tag_removal_does_not_delete_essay(self, essay_with_tags):
        """Removing a tag from an essay does not delete the essay itself."""
        tag = essay_with_tags.tags.first()
        essay_with_tags.tags.remove(tag)
        essay_with_tags.refresh_from_db()
        assert essay_with_tags.pk is not None
