"""
Factory Boy Factories
=====================

Factories for the content publishing site models. These produce realistic
test data without touching the database until .create() is called.

Patterns demonstrated:
    - Faker providers for realistic field values
    - SubFactory for ForeignKey relationships
    - LazyAttribute for computed fields (slug from title)
    - Sequence for guaranteed-unique values
    - Traits for model state variants (draft, published, archived)
    - post_generation for M2M relationships
    - RelatedFactory and RelatedFactoryList for reverse relations

Usage:
    # Build in memory (no DB hit)
    essay = EssayFactory.build()

    # Create in database
    essay = EssayFactory.create()

    # Create with overrides
    essay = EssayFactory(title="Custom Title", stage="published")

    # Create a batch
    essays = EssayFactory.create_batch(10)

    # Use traits
    essay = EssayFactory(published=True)
    essay = EssayFactory(archived=True)
"""

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from factory.django import DjangoModelFactory

from apps.content.models import Essay, Tag

User = get_user_model()


# ---------------------------------------------------------------------------
# UserFactory
# ---------------------------------------------------------------------------


class UserFactory(DjangoModelFactory):
    """
    Factory for Django's User model.

    Uses Faker providers for realistic names and emails.
    Sequence ensures unique usernames across a test run.
    """

    class Meta:
        model = User
        # skip_postgeneration_save avoids an extra .save() call after
        # post_generation hooks run. Available in factory_boy >= 3.3.
        skip_postgeneration_save = True

    # Sequence guarantees uniqueness even if Faker produces duplicates.
    username = factory.Sequence(lambda n: f"user-{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """
        Set a usable password. If a raw password string is passed,
        use it; otherwise default to 'testpass123'.

        Usage:
            UserFactory(password="custom-pass")
            UserFactory()  # password is 'testpass123'
        """
        raw = extracted or "testpass123"
        self.set_password(raw)
        if create:
            self.save(update_fields=["password"])


# ---------------------------------------------------------------------------
# TagFactory
# ---------------------------------------------------------------------------


class TagFactory(DjangoModelFactory):
    """
    Factory for Tag model.

    Sequence produces unique tag names: tag-0, tag-1, tag-2, ...
    LazyAttribute derives the slug from the name.
    """

    class Meta:
        model = Tag
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"tag-{n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))


# ---------------------------------------------------------------------------
# EssayFactory
# ---------------------------------------------------------------------------


class EssayFactory(DjangoModelFactory):
    """
    Factory for Essay model.

    Demonstrates:
    - SubFactory for the author ForeignKey
    - LazyAttribute for slug derived from title
    - Faker for realistic text content
    - Traits for different essay lifecycle states
    """

    class Meta:
        model = Essay
        skip_postgeneration_save = True

    # SubFactory creates a User automatically if none is provided.
    author = factory.SubFactory(UserFactory)

    title = factory.Faker("sentence", nb_words=6)
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title)[:80])
    summary = factory.Faker("paragraph", nb_sentences=3)
    body = factory.Faker("text", max_nb_chars=2000)
    stage = "draft"
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)
    published_at = None
    word_count = factory.LazyAttribute(
        lambda obj: len(obj.body.split()) if obj.body else 0
    )

    class Params:
        """
        Traits let you toggle a named set of field overrides.

        Usage:
            EssayFactory(published=True)   # stage='published', published_at set
            EssayFactory(archived=True)    # stage='archived'
            EssayFactory(draft=True)       # stage='draft' (the default anyway)
        """

        draft = factory.Trait(
            stage="draft",
            published_at=None,
        )

        published = factory.Trait(
            stage="published",
            published_at=factory.LazyFunction(timezone.now),
        )

        archived = factory.Trait(
            stage="archived",
            published_at=factory.LazyFunction(timezone.now),
        )


# ---------------------------------------------------------------------------
# EssayWithTagsFactory -- M2M through post_generation
# ---------------------------------------------------------------------------


class EssayWithTagsFactory(EssayFactory):
    """
    An essay that comes pre-loaded with tags.

    Demonstrates post_generation for many-to-many relationships.

    Usage:
        # Default: creates 3 tags and attaches them.
        essay = EssayWithTagsFactory()

        # Explicit tags:
        t1 = TagFactory(name="python")
        t2 = TagFactory(name="django")
        essay = EssayWithTagsFactory(tags=[t1, t2])
    """

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if not create:
            # build() was called, not create(). M2M needs a PK.
            return

        if extracted:
            # An explicit list of tags was passed in.
            self.tags.add(*extracted)
        else:
            # Default: generate 3 tags and attach them.
            self.tags.add(*TagFactory.create_batch(3))


# ---------------------------------------------------------------------------
# Patterns: RelatedFactory and RelatedFactoryList
# ---------------------------------------------------------------------------


class AuthorWithEssaysFactory(UserFactory):
    """
    A user who already has essays.

    RelatedFactoryList creates multiple related objects pointing
    back at this user. Useful when you need a user with pre-existing
    content for list/search tests.

    Usage:
        author = AuthorWithEssaysFactory()
        assert author.essays.count() == 3
    """

    essays = factory.RelatedFactoryList(
        "testing_patterns.factories.EssayFactory",
        factory_related_name="author",
        size=3,
    )


class EssayWithSpecificAuthorFactory(DjangoModelFactory):
    """
    Demonstrates RelatedFactory (singular) for creating exactly one
    related object with specific attributes.
    """

    class Meta:
        model = Essay
        skip_postgeneration_save = True

    author = factory.SubFactory(
        UserFactory,
        username="specific-author",
        email="specific@example.com",
    )
    title = factory.Sequence(lambda n: f"Essay by specific author #{n}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.title)[:80])
    body = factory.Faker("text", max_nb_chars=500)
    stage = "draft"
    created_at = factory.LazyFunction(timezone.now)
    updated_at = factory.LazyFunction(timezone.now)


# ---------------------------------------------------------------------------
# Utility: Faker locale and seed control
# ---------------------------------------------------------------------------

# To get reproducible test data, seed Faker at the module level:
#
#   factory.Faker._DEFAULT_LOCALE = "en_US"
#   factory.random.reseed_random(42)
#
# This makes factory output deterministic across runs, which is helpful
# for snapshot testing or debugging flaky tests.
