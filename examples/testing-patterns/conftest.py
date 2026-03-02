"""
Pytest-Django Configuration and Fixtures
=========================================

Central fixture definitions for the content publishing site test suite.
All fixtures use pytest-django conventions. Factories are defined in
factories.py and wrapped here as fixtures for dependency injection.

Usage:
    Fixtures are auto-discovered by pytest from this conftest.py.
    Import nothing -- just declare fixture names as test parameters.
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.content.models import Essay, Tag

from .factories import (
    EssayFactory,
    EssayWithTagsFactory,
    TagFactory,
    UserFactory,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Database setup: session-scoped fixture for expensive one-time work
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def django_db_setup(django_test_environment, django_db_blocker):
    """
    Session-scoped database setup. Runs once per test session.

    Use this for expensive seed data that every test needs but that
    no test mutates. For mutable data, use function-scoped fixtures.
    """
    with django_db_blocker.unblock():
        # Create a set of canonical tags that many tests reference.
        # These survive the entire session because no test deletes them.
        for name in ("python", "django", "testing", "deployment"):
            Tag.objects.get_or_create(name=name, defaults={"slug": name})


# ---------------------------------------------------------------------------
# Autouse fixture: runs before every test automatically
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_caches():
    """
    Autouse fixture that clears Django caches between tests.

    Yields control to the test, then tears down afterward.
    The leading underscore signals that tests should not request
    this fixture by name -- it runs automatically.
    """
    yield
    # Teardown: clear caches so tests do not leak state.
    from django.core.cache import cache

    cache.clear()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    """A plain, non-staff user."""
    return UserFactory()


@pytest.fixture
def author(db):
    """A user who has authored content. Alias kept for readability."""
    return UserFactory(username="essay-author", email="author@example.com")


@pytest.fixture
def staff_user(db):
    """A staff user for admin-level tests."""
    return UserFactory(is_staff=True, username="staff-user")


@pytest.fixture
def superuser(db):
    """A superuser for permission boundary tests."""
    return UserFactory(is_staff=True, is_superuser=True, username="super-user")


# ---------------------------------------------------------------------------
# Tag fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tag(db):
    """A single tag instance."""
    return TagFactory()


@pytest.fixture
def tag_python(db):
    """The canonical 'python' tag, fetched or created."""
    obj, _ = Tag.objects.get_or_create(name="python", defaults={"slug": "python"})
    return obj


@pytest.fixture
def tag_django(db):
    """The canonical 'django' tag, fetched or created."""
    obj, _ = Tag.objects.get_or_create(name="django", defaults={"slug": "django"})
    return obj


# ---------------------------------------------------------------------------
# Essay fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def essay(db, author):
    """A draft essay owned by the author fixture."""
    return EssayFactory(author=author)


@pytest.fixture
def published_essay(db, author):
    """A published essay with a publish date set."""
    return EssayFactory(author=author, stage="published")


# ---------------------------------------------------------------------------
# Composed fixtures: essay_with_tags depends on essay + tag fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def essay_with_tags(db, author, tag_python, tag_django):
    """
    An essay that already has tags attached.

    Demonstrates fixture composition -- this fixture depends on author,
    tag_python, and tag_django. Pytest resolves the dependency graph
    automatically.
    """
    obj = EssayFactory(author=author)
    obj.tags.add(tag_python, tag_django)
    return obj


@pytest.fixture
def essay_batch(db, author):
    """A batch of 5 essays for pagination and list tests."""
    return EssayFactory.create_batch(5, author=author)


# ---------------------------------------------------------------------------
# Factory fixtures (expose factories directly for one-off customization)
# ---------------------------------------------------------------------------


@pytest.fixture
def make_user():
    """
    Factory-as-fixture pattern. Returns the factory callable so tests
    can create users with custom attributes inline.

    Usage in tests:
        def test_something(make_user):
            admin = make_user(is_staff=True)
            regular = make_user()
    """
    return UserFactory


@pytest.fixture
def make_essay():
    """Factory-as-fixture for essays."""
    return EssayFactory


@pytest.fixture
def make_tag():
    """Factory-as-fixture for tags."""
    return TagFactory


# ---------------------------------------------------------------------------
# API client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    """
    An anonymous (unauthenticated) DRF API client.

    Use this for testing public endpoints or verifying that
    authentication is enforced.
    """
    return APIClient()


@pytest.fixture
def authenticated_client(user):
    """
    An API client authenticated as a regular user.

    force_authenticate bypasses the authentication backend entirely,
    which is appropriate for tests that are not testing auth itself.
    """
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def author_client(author):
    """
    An API client authenticated as the essay author.

    Use this to test owner-only operations (update, delete).
    """
    client = APIClient()
    client.force_authenticate(user=author)
    return client


@pytest.fixture
def staff_client(staff_user):
    """An API client authenticated as a staff user."""
    client = APIClient()
    client.force_authenticate(user=staff_user)
    return client


# ---------------------------------------------------------------------------
# Transactional test case fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def transactional(transactional_db):
    """
    Marker fixture for tests that need real transactions.

    Most tests use the default `db` fixture, which wraps each test in a
    transaction that is rolled back. Use `transactional` when:
    - Testing code that uses transaction.on_commit()
    - Testing code that spawns threads or subprocesses
    - Testing Celery tasks that hit the database

    Usage:
        def test_on_commit_callback(transactional, essay):
            ...
    """
    pass


# ---------------------------------------------------------------------------
# Django test client fixture (for non-API view tests)
# ---------------------------------------------------------------------------


@pytest.fixture
def web_client(db):
    """Standard Django test client for template/view tests."""
    from django.test import Client

    return Client()


@pytest.fixture
def authenticated_web_client(user):
    """Django test client logged in as a regular user."""
    from django.test import Client

    client = Client()
    client.force_login(user)
    return client
