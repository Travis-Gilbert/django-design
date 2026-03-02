"""
DRF API Testing Patterns
========================

Tests for the Essay and Tag REST API endpoints.

Patterns demonstrated:
    - Testing full CRUD lifecycle (list, create, retrieve, update, delete)
    - Permission testing (anonymous, authenticated, author, staff)
    - Filtering and search query parameters
    - Pagination assertions
    - Nested serializer behavior
    - Custom viewset actions
    - DRF status constants for readable assertions
    - Using api_client, authenticated_client, and author_client fixtures

Conventions:
    - Each test class covers one endpoint or permission boundary
    - Tests use reverse() for URL resolution when possible
    - Response data is checked for structure and content, not just status
"""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.content.models import Essay, Tag

from .factories import EssayFactory, TagFactory, UserFactory


# ===========================================================================
# Essay List Endpoint
# ===========================================================================


@pytest.mark.django_db
class TestEssayListEndpoint:
    """GET /api/essays/ -- list essays."""

    url = reverse("essay-list")

    def test_list_returns_200(self, api_client):
        """Public endpoint returns 200 even for anonymous users."""
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK

    def test_list_returns_only_published_essays(self, api_client, author):
        """The list endpoint should only show published essays."""
        EssayFactory(author=author, stage="draft")
        EssayFactory(author=author, stage="published")
        EssayFactory(author=author, stage="archived")

        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

    def test_list_contains_expected_fields(self, api_client, published_essay):
        """Response includes the expected serializer fields."""
        response = api_client.get(self.url)
        essay_data = response.data["results"][0]

        expected_fields = {
            "id", "title", "slug", "summary", "author",
            "stage", "tags", "created_at", "word_count",
        }
        assert expected_fields.issubset(set(essay_data.keys()))

    def test_list_does_not_include_body(self, api_client, published_essay):
        """The list serializer omits the full body for performance."""
        response = api_client.get(self.url)
        essay_data = response.data["results"][0]
        assert "body" not in essay_data


# ===========================================================================
# Essay Create Endpoint
# ===========================================================================


@pytest.mark.django_db
class TestEssayCreateEndpoint:
    """POST /api/essays/ -- create a new essay."""

    url = reverse("essay-list")

    def test_anonymous_cannot_create(self, api_client):
        """Anonymous users get 401 when trying to create."""
        payload = {"title": "Test Essay", "body": "Content here."}
        response = api_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_authenticated_user_can_create(self, authenticated_client):
        """Authenticated users can create essays."""
        payload = {
            "title": "My New Essay",
            "body": "The body of the essay.",
            "summary": "A brief summary.",
        }
        response = authenticated_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "My New Essay"
        assert response.data["stage"] == "draft"

    def test_create_auto_sets_author_to_current_user(self, authenticated_client, user):
        """The author field is automatically set to the requesting user."""
        payload = {"title": "Auto Author", "body": "Content."}
        response = authenticated_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["author"]["id"] == user.pk

    def test_create_auto_generates_slug(self, authenticated_client):
        """If slug is omitted, one is generated from the title."""
        payload = {"title": "Slug Generation Test", "body": "Content."}
        response = authenticated_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "slug-generation-test"

    def test_create_with_tags(self, authenticated_client):
        """Tags can be attached by name during creation."""
        TagFactory(name="python", slug="python")
        TagFactory(name="testing", slug="testing")

        payload = {
            "title": "Tagged Essay",
            "body": "Content.",
            "tags": ["python", "testing"],
        }
        response = authenticated_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data["tags"]) == 2

    def test_create_validates_required_fields(self, authenticated_client):
        """Missing required fields return 400 with field errors."""
        response = authenticated_client.post(self.url, {}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "title" in response.data


# ===========================================================================
# Essay Retrieve Endpoint
# ===========================================================================


@pytest.mark.django_db
class TestEssayRetrieveEndpoint:
    """GET /api/essays/<slug>/ -- retrieve a single essay."""

    def test_retrieve_published_essay(self, api_client, published_essay):
        """Anyone can retrieve a published essay by slug."""
        url = reverse("essay-detail", kwargs={"slug": published_essay.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == published_essay.title

    def test_retrieve_includes_body(self, api_client, published_essay):
        """The detail serializer includes the full body text."""
        url = reverse("essay-detail", kwargs={"slug": published_essay.slug})
        response = api_client.get(url)
        assert "body" in response.data

    def test_retrieve_draft_returns_404_for_anonymous(self, api_client, essay):
        """Anonymous users cannot see draft essays."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_draft_visible_to_author(self, author_client, essay):
        """The essay author can see their own drafts."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = author_client.get(url)
        assert response.status_code == status.HTTP_200_OK

    def test_retrieve_nonexistent_returns_404(self, api_client):
        """A missing slug returns 404, not 500."""
        url = reverse("essay-detail", kwargs={"slug": "does-not-exist"})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Essay Update Endpoint
# ===========================================================================


@pytest.mark.django_db
class TestEssayUpdateEndpoint:
    """PUT/PATCH /api/essays/<slug>/ -- update an essay."""

    def test_author_can_update_own_essay(self, author_client, essay):
        """The essay author can update their own essay."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = author_client.patch(
            url,
            {"title": "Updated Title"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Updated Title"

    def test_non_author_cannot_update(self, authenticated_client, essay):
        """A user who is not the author gets 403."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = authenticated_client.patch(
            url,
            {"title": "Hijacked Title"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_cannot_update(self, api_client, essay):
        """Anonymous users get 401."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = api_client.patch(
            url,
            {"title": "Anon Update"},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_can_update_any_essay(self, staff_client, essay):
        """Staff users can update any essay regardless of ownership."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = staff_client.patch(
            url,
            {"title": "Staff Edit"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_partial_update_preserves_other_fields(self, author_client, essay):
        """PATCH only changes the specified fields."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        original_body = essay.body

        author_client.patch(url, {"title": "New Title"}, format="json")

        essay.refresh_from_db()
        assert essay.title == "New Title"
        assert essay.body == original_body


# ===========================================================================
# Essay Delete Endpoint
# ===========================================================================


@pytest.mark.django_db
class TestEssayDeleteEndpoint:
    """DELETE /api/essays/<slug>/ -- delete an essay."""

    def test_author_can_delete_own_essay(self, author_client, essay):
        """The essay author can delete their own essay."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = author_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Essay.objects.filter(slug=essay.slug).exists()

    def test_non_author_cannot_delete(self, authenticated_client, essay):
        """Non-authors get 403 on delete."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_anonymous_cannot_delete(self, api_client, essay):
        """Anonymous users get 401 on delete."""
        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# Filtering and Search
# ===========================================================================


@pytest.mark.django_db
class TestEssayFiltering:
    """GET /api/essays/?<filter> -- query parameter filtering."""

    url = reverse("essay-list")

    def test_filter_by_tag(self, api_client, author):
        """Filter essays by tag name using ?tag=python."""
        tag = TagFactory(name="python", slug="python")
        essay = EssayFactory(author=author, stage="published")
        essay.tags.add(tag)
        EssayFactory(author=author, stage="published")  # No tags

        response = api_client.get(self.url, {"tag": "python"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["slug"] == essay.slug

    def test_filter_by_author_username(self, api_client, author):
        """Filter essays by author username using ?author=<username>."""
        EssayFactory(author=author, stage="published")
        other = UserFactory()
        EssayFactory(author=other, stage="published")

        response = api_client.get(self.url, {"author": author.username})
        assert len(response.data["results"]) == 1

    def test_search_by_title(self, api_client, author):
        """Full-text search on title using ?search=<query>."""
        EssayFactory(
            author=author,
            title="Django Testing Guide",
            stage="published",
        )
        EssayFactory(
            author=author,
            title="Cooking Recipes",
            stage="published",
        )

        response = api_client.get(self.url, {"search": "Django"})
        assert len(response.data["results"]) == 1
        assert "Django" in response.data["results"][0]["title"]

    def test_ordering_by_created_at(self, api_client, author):
        """Results can be ordered by created_at using ?ordering=."""
        EssayFactory(author=author, title="Older", stage="published")
        EssayFactory(author=author, title="Newer", stage="published")

        response = api_client.get(self.url, {"ordering": "-created_at"})
        titles = [e["title"] for e in response.data["results"]]
        assert titles[0] == "Newer"

    def test_invalid_filter_is_ignored(self, api_client, published_essay):
        """Unknown query parameters do not cause errors."""
        response = api_client.get(self.url, {"bogus": "value"})
        assert response.status_code == status.HTTP_200_OK


# ===========================================================================
# Pagination
# ===========================================================================


@pytest.mark.django_db
class TestEssayPagination:
    """Pagination behavior on the essay list endpoint."""

    url = reverse("essay-list")

    def test_default_page_size(self, api_client, author):
        """Default page size is 20 (configurable in settings)."""
        EssayFactory.create_batch(25, author=author, stage="published")

        response = api_client.get(self.url)
        assert len(response.data["results"]) == 20
        assert response.data["count"] == 25

    def test_next_page_link_present(self, api_client, author):
        """When more results exist, 'next' contains a URL."""
        EssayFactory.create_batch(25, author=author, stage="published")

        response = api_client.get(self.url)
        assert response.data["next"] is not None

    def test_page_parameter(self, api_client, author):
        """?page=2 returns the second page of results."""
        EssayFactory.create_batch(25, author=author, stage="published")

        response = api_client.get(self.url, {"page": 2})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5  # 25 total, 20 per page

    def test_custom_page_size(self, api_client, author):
        """?page_size=5 overrides the default page size."""
        EssayFactory.create_batch(10, author=author, stage="published")

        response = api_client.get(self.url, {"page_size": 5})
        assert len(response.data["results"]) == 5

    def test_empty_page_returns_404(self, api_client, author):
        """Requesting a page beyond the last returns 404."""
        EssayFactory.create_batch(3, author=author, stage="published")

        response = api_client.get(self.url, {"page": 99})
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# Nested Serializer Behavior
# ===========================================================================


@pytest.mark.django_db
class TestNestedSerializers:
    """Test how nested relationships are serialized."""

    def test_author_is_nested_object(self, api_client, published_essay):
        """The author field is a nested object, not just an ID."""
        url = reverse("essay-detail", kwargs={"slug": published_essay.slug})
        response = api_client.get(url)

        author_data = response.data["author"]
        assert isinstance(author_data, dict)
        assert "id" in author_data
        assert "username" in author_data

    def test_tags_are_list_of_objects(self, api_client, author):
        """Tags are serialized as a list of {name, slug} objects."""
        tag = TagFactory(name="python", slug="python")
        essay = EssayFactory(author=author, stage="published")
        essay.tags.add(tag)

        url = reverse("essay-detail", kwargs={"slug": essay.slug})
        response = api_client.get(url)

        tags_data = response.data["tags"]
        assert isinstance(tags_data, list)
        assert tags_data[0]["name"] == "python"
        assert tags_data[0]["slug"] == "python"


# ===========================================================================
# Custom Actions
# ===========================================================================


@pytest.mark.django_db
class TestEssayCustomActions:
    """Tests for custom viewset actions (@action decorator)."""

    def test_publish_action(self, author_client, essay):
        """
        POST /api/essays/<slug>/publish/ transitions a draft to published.

        This tests a custom @action on the EssayViewSet.
        """
        url = reverse("essay-publish", kwargs={"slug": essay.slug})
        response = author_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["stage"] == "published"

        essay.refresh_from_db()
        assert essay.stage == "published"
        assert essay.published_at is not None

    def test_publish_action_requires_author(self, authenticated_client, essay):
        """Only the author can trigger the publish action."""
        url = reverse("essay-publish", kwargs={"slug": essay.slug})
        response = authenticated_client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_archive_action(self, author_client, published_essay):
        """POST /api/essays/<slug>/archive/ moves to archived stage."""
        url = reverse("essay-archive", kwargs={"slug": published_essay.slug})
        response = author_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["stage"] == "archived"

    def test_stats_action_returns_aggregate_data(self, api_client, author):
        """
        GET /api/essays/stats/ returns aggregate statistics.

        This is a list-level custom action (detail=False).
        """
        EssayFactory.create_batch(5, author=author, stage="published")

        url = reverse("essay-stats")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "total_published" in response.data
        assert response.data["total_published"] == 5


# ===========================================================================
# Tag API Endpoint
# ===========================================================================


@pytest.mark.django_db
class TestTagEndpoint:
    """Tests for the Tag API (read-only for non-staff users)."""

    url = reverse("tag-list")

    def test_list_tags(self, api_client):
        """Anyone can list tags."""
        TagFactory.create_batch(5)
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 5

    def test_retrieve_tag(self, api_client):
        """Anyone can retrieve a single tag."""
        tag = TagFactory(name="python", slug="python")
        url = reverse("tag-detail", kwargs={"slug": tag.slug})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "python"

    def test_anonymous_cannot_create_tag(self, api_client):
        """Tag creation requires authentication."""
        response = api_client.post(self.url, {"name": "new-tag"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_staff_can_create_tag(self, staff_client):
        """Staff users can create tags."""
        response = staff_client.post(
            self.url,
            {"name": "new-tag", "slug": "new-tag"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Tag.objects.filter(name="new-tag").exists()

    def test_non_staff_cannot_delete_tag(self, authenticated_client):
        """Regular users cannot delete tags."""
        tag = TagFactory()
        url = reverse("tag-detail", kwargs={"slug": tag.slug})
        response = authenticated_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
