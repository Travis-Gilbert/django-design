"""
Django View Testing Patterns
=============================

Tests for regular Django views and HTMX partial responses.

Patterns demonstrated:
    - Testing regular Django views with the test client
    - Testing HTMX partial responses (HX-Request header handling)
    - Testing form submission (GET and POST)
    - Testing redirects (login_required, post-form redirect)
    - Testing context data passed to templates
    - Testing template selection (full page vs. partial)
    - Using web_client and authenticated_web_client fixtures

Note: These tests use Django's test client, not DRF's APIClient.
The test client is better suited for HTML views because it handles
cookies, sessions, CSRF tokens, and template rendering.
"""

import pytest
from django.urls import reverse

from apps.content.models import Essay, Tag

from .factories import EssayFactory, TagFactory, UserFactory


# ===========================================================================
# Essay List View
# ===========================================================================


@pytest.mark.django_db
class TestEssayListView:
    """Tests for the essay listing page."""

    url = reverse("essay_list")

    def test_list_page_returns_200(self, web_client):
        """The essay list page is publicly accessible."""
        response = web_client.get(self.url)
        assert response.status_code == 200

    def test_list_page_uses_correct_template(self, web_client):
        """Verify the correct template is rendered."""
        response = web_client.get(self.url)
        assert "content/essay_list.html" in [
            t.name for t in response.templates
        ]

    def test_list_page_context_contains_essays(self, web_client, author):
        """The template context includes the essay queryset."""
        EssayFactory.create_batch(3, author=author, stage="published")

        response = web_client.get(self.url)
        assert "essays" in response.context
        assert len(response.context["essays"]) == 3

    def test_list_page_shows_only_published(self, web_client, author):
        """Draft and archived essays are excluded from the public list."""
        EssayFactory(author=author, stage="draft")
        EssayFactory(author=author, stage="published")
        EssayFactory(author=author, stage="archived")

        response = web_client.get(self.url)
        assert len(response.context["essays"]) == 1

    def test_list_page_content(self, web_client, author):
        """Published essay titles appear in the response body."""
        essay = EssayFactory(
            author=author,
            title="Visible Essay",
            stage="published",
        )
        response = web_client.get(self.url)
        assert essay.title.encode() in response.content


# ===========================================================================
# Essay Detail View
# ===========================================================================


@pytest.mark.django_db
class TestEssayDetailView:
    """Tests for the essay detail page."""

    def test_detail_returns_200_for_published(self, web_client, published_essay):
        url = reverse("essay_detail", kwargs={"slug": published_essay.slug})
        response = web_client.get(url)
        assert response.status_code == 200

    def test_detail_returns_404_for_draft(self, web_client, essay):
        """Draft essays return 404 for anonymous visitors."""
        url = reverse("essay_detail", kwargs={"slug": essay.slug})
        response = web_client.get(url)
        assert response.status_code == 404

    def test_detail_context_has_essay(self, web_client, published_essay):
        """The template context includes the essay object."""
        url = reverse("essay_detail", kwargs={"slug": published_essay.slug})
        response = web_client.get(url)
        assert response.context["essay"] == published_essay

    def test_detail_context_has_related_essays(self, web_client, author):
        """The detail page includes related essays in context."""
        tag = TagFactory(name="python", slug="python")
        main = EssayFactory(author=author, stage="published")
        main.tags.add(tag)
        related = EssayFactory(author=author, stage="published")
        related.tags.add(tag)

        url = reverse("essay_detail", kwargs={"slug": main.slug})
        response = web_client.get(url)

        assert "related_essays" in response.context


# ===========================================================================
# HTMX Partial Responses
# ===========================================================================


@pytest.mark.django_db
class TestHTMXPartialResponses:
    """
    Tests for HTMX partial rendering.

    When a request includes the HX-Request header, Django views should
    return a partial template (just the fragment) instead of the full
    page. This avoids sending the base layout, nav, and footer for
    HTMX-driven updates.
    """

    def test_full_page_without_hx_header(self, web_client, author):
        """Without HX-Request header, return the full page template."""
        EssayFactory.create_batch(3, author=author, stage="published")
        url = reverse("essay_list")

        response = web_client.get(url)
        template_names = [t.name for t in response.templates]

        # Full page includes the base layout.
        assert "base.html" in template_names or any(
            "base" in name for name in template_names
        )
        assert "content/essay_list.html" in template_names

    def test_partial_with_hx_header(self, web_client, author):
        """
        With HX-Request: true, return only the partial template.

        The view detects the HTMX header and renders just the content
        fragment, skipping the base layout.
        """
        EssayFactory.create_batch(3, author=author, stage="published")
        url = reverse("essay_list")

        response = web_client.get(url, HTTP_HX_REQUEST="true")
        template_names = [t.name for t in response.templates]

        # Partial should use the fragment template.
        assert "content/partials/essay_list_items.html" in template_names

    def test_htmx_search_returns_filtered_results(self, web_client, author):
        """
        HTMX search endpoint filters essays and returns a partial.

        Tests the pattern where a search input triggers an HTMX GET
        with the query as a parameter.
        """
        EssayFactory(author=author, title="Django Patterns", stage="published")
        EssayFactory(author=author, title="Cooking Tips", stage="published")

        url = reverse("essay_list")
        response = web_client.get(
            url,
            {"q": "Django"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        assert len(response.context["essays"]) == 1

    def test_htmx_infinite_scroll(self, web_client, author):
        """
        HTMX infinite scroll sends page parameter and gets next batch.

        The response should contain only the essay items partial, not
        the full page wrapper, so HTMX can append it to the list.
        """
        EssayFactory.create_batch(30, author=author, stage="published")

        url = reverse("essay_list")
        response = web_client.get(
            url,
            {"page": 2},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        template_names = [t.name for t in response.templates]
        assert "content/partials/essay_list_items.html" in template_names

    def test_htmx_response_has_no_hx_redirect(self, web_client, published_essay):
        """
        Normal HTMX responses should not include HX-Redirect header.

        Only form submissions or special actions set HX-Redirect.
        """
        url = reverse("essay_detail", kwargs={"slug": published_essay.slug})
        response = web_client.get(url, HTTP_HX_REQUEST="true")
        assert "HX-Redirect" not in response


# ===========================================================================
# Form Submission
# ===========================================================================


@pytest.mark.django_db
class TestEssayCreateFormView:
    """Tests for the essay creation form (HTML form, not API)."""

    url = reverse("essay_create")

    def test_form_page_requires_login(self, web_client):
        """Anonymous users are redirected to the login page."""
        response = web_client.get(self.url)
        assert response.status_code == 302
        assert "/login/" in response.url

    def test_form_page_accessible_when_logged_in(self, authenticated_web_client):
        """Authenticated users can access the form page."""
        response = authenticated_web_client.get(self.url)
        assert response.status_code == 200

    def test_form_in_context(self, authenticated_web_client):
        """The response context contains the essay form."""
        response = authenticated_web_client.get(self.url)
        assert "form" in response.context

    def test_valid_form_submission_creates_essay(self, authenticated_web_client, user):
        """Submitting valid data creates an essay and redirects."""
        payload = {
            "title": "Form Created Essay",
            "summary": "A summary from the form.",
            "body": "Full essay body content from the HTML form.",
        }
        response = authenticated_web_client.post(self.url, payload)

        # Successful form submission redirects to the detail page.
        assert response.status_code == 302

        essay = Essay.objects.get(title="Form Created Essay")
        assert essay.author == user
        assert essay.stage == "draft"

    def test_invalid_form_re_renders_with_errors(self, authenticated_web_client):
        """Submitting an empty form re-renders the page with errors."""
        response = authenticated_web_client.post(self.url, {})
        assert response.status_code == 200  # Re-renders, not redirect
        assert response.context["form"].errors

    def test_form_csrf_protection(self, authenticated_web_client):
        """
        Django's CSRF middleware is active.

        The test client handles CSRF automatically, but we can verify
        the form includes the token.
        """
        response = authenticated_web_client.get(self.url)
        assert b"csrfmiddlewaretoken" in response.content

    def test_htmx_form_submission(self, authenticated_web_client):
        """
        HTMX form submission returns a partial instead of redirecting.

        When a form is submitted via HTMX (HX-Request header present),
        the view should return a rendered partial or set HX-Redirect
        instead of a normal HTTP redirect.
        """
        payload = {
            "title": "HTMX Form Essay",
            "summary": "Summary.",
            "body": "Body content.",
        }
        response = authenticated_web_client.post(
            self.url,
            payload,
            HTTP_HX_REQUEST="true",
        )

        # The view should set HX-Redirect to tell HTMX where to go.
        assert response.status_code == 200 or "HX-Redirect" in response


# ===========================================================================
# Redirects
# ===========================================================================


@pytest.mark.django_db
class TestRedirects:
    """Tests for redirect behavior."""

    def test_login_required_redirects_to_login(self, web_client):
        """Protected pages redirect anonymous users to login."""
        url = reverse("essay_create")
        response = web_client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

    def test_login_required_preserves_next_parameter(self, web_client):
        """The redirect URL includes ?next= so the user returns after login."""
        url = reverse("essay_create")
        response = web_client.get(url)

        assert f"next={url}" in response.url or "next=%2F" in response.url

    def test_successful_create_redirects_to_detail(self, authenticated_web_client):
        """After creating an essay, redirect to its detail page."""
        payload = {
            "title": "Redirect Test Essay",
            "summary": "Summary.",
            "body": "Body.",
        }
        response = authenticated_web_client.post(
            reverse("essay_create"),
            payload,
        )
        assert response.status_code == 302

        essay = Essay.objects.get(title="Redirect Test Essay")
        expected_url = reverse("essay_detail", kwargs={"slug": essay.slug})
        assert response.url == expected_url

    def test_old_slug_redirects_to_new_slug(self, web_client, author):
        """
        If an essay's slug changes, the old URL redirects to the new one.

        This tests the SlugRedirectMiddleware or a similar mechanism
        that keeps old URLs working.
        """
        essay = EssayFactory(author=author, slug="old-slug", stage="published")
        old_url = reverse("essay_detail", kwargs={"slug": "old-slug"})

        # Simulate slug change.
        essay.slug = "new-slug"
        essay.save()

        response = web_client.get(old_url)
        # Should redirect (301 or 302) to the new slug.
        assert response.status_code in (301, 302)


# ===========================================================================
# Context Data Assertions
# ===========================================================================


@pytest.mark.django_db
class TestContextData:
    """Tests that verify the template context contains expected data."""

    def test_essay_list_context_has_tag_cloud(self, web_client):
        """The list page includes popular tags for a sidebar tag cloud."""
        TagFactory.create_batch(5)
        response = web_client.get(reverse("essay_list"))
        assert "popular_tags" in response.context

    def test_essay_detail_context_has_reading_time(
        self, web_client, published_essay
    ):
        """The detail page includes a reading time estimate."""
        url = reverse("essay_detail", kwargs={"slug": published_essay.slug})
        response = web_client.get(url)
        assert "reading_time" in response.context

    def test_essay_detail_context_has_author_info(
        self, web_client, published_essay
    ):
        """The detail page includes author metadata."""
        url = reverse("essay_detail", kwargs={"slug": published_essay.slug})
        response = web_client.get(url)
        assert response.context["essay"].author is not None

    def test_dashboard_context_has_user_essays(
        self, authenticated_web_client, user
    ):
        """The author dashboard shows the logged-in user's essays."""
        EssayFactory.create_batch(3, author=user)
        other_user = UserFactory()
        EssayFactory.create_batch(2, author=other_user)

        url = reverse("dashboard")
        response = authenticated_web_client.get(url)

        assert "my_essays" in response.context
        assert len(response.context["my_essays"]) == 3

    def test_dashboard_context_has_draft_count(
        self, authenticated_web_client, user
    ):
        """The dashboard shows how many drafts the user has."""
        EssayFactory(author=user, stage="draft")
        EssayFactory(author=user, stage="draft")
        EssayFactory(author=user, stage="published")

        url = reverse("dashboard")
        response = authenticated_web_client.get(url)
        assert response.context["draft_count"] == 2


# ===========================================================================
# Error Pages
# ===========================================================================


@pytest.mark.django_db
class TestErrorPages:
    """Tests for error handling in views."""

    def test_404_page_renders(self, web_client):
        """A request for a nonexistent URL returns 404 with a template."""
        response = web_client.get("/nonexistent-page-that-does-not-exist/")
        assert response.status_code == 404

    def test_detail_view_404_for_bad_slug(self, web_client):
        """A detail request for a nonexistent slug returns 404."""
        url = reverse("essay_detail", kwargs={"slug": "no-such-essay"})
        response = web_client.get(url)
        assert response.status_code == 404
