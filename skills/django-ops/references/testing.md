# Django Testing Strategy Reference

## Core Principle

Prioritize testing business logic, not Django machinery. Models and domain logic get thorough tests. Template rendering and URL routing get smoke tests. Do not test that the ORM works.

## Test Organization

```
apps/your_app/tests/
    __init__.py
    test_models.py      # model methods, managers, constraints
    test_views.py       # request/response, permissions, redirects
    test_api.py         # DRF serializers, ViewSets, API responses
    test_services.py    # service layer business logic
    test_forms.py       # form validation (if using Django forms)
    test_commands.py    # management command tests
    factories.py        # factory_boy factories
    conftest.py         # pytest fixtures (if using pytest)
```

## factory_boy Over Fixtures

Use `factory_boy` for test data, not JSON fixtures. Factories compose better and make tests self-documenting.

```python
# tests/factories.py
import factory
from apps.content.models import Essay, VideoProject
from apps.research.models import Source, SourceLink


class EssayFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Essay

    title = factory.Faker('sentence', nb_words=5)
    slug = factory.Sequence(lambda n: f'essay-{n}')
    stage = 'drafting'
    draft = True
    date = factory.Faker('date_this_year')
    summary = factory.Faker('paragraph')
    body = factory.Faker('text', max_nb_chars=2000)
    tags = factory.LazyFunction(lambda: ['design', 'systems'])


class SourceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Source

    title = factory.Faker('sentence', nb_words=4)
    slug = factory.Sequence(lambda n: f'source-{n}')
    source_type = 'article'
    url = factory.Faker('url')
    creator = factory.Faker('name')


class SourceLinkFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SourceLink

    source = factory.SubFactory(SourceFactory)
    content_type = 'essay'
    content_slug = factory.Sequence(lambda n: f'essay-{n}')
    content_title = factory.Faker('sentence', nb_words=5)
    role = 'primary'
```

### Advanced Factory Patterns

```python
class EssayFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Essay

    # Traits: named presets for common scenarios
    class Params:
        published = factory.Trait(
            stage='published',
            draft=False,
            date=factory.Faker('date_this_year'),
        )
        in_research = factory.Trait(
            stage='research',
            draft=True,
        )
        with_sources = factory.Trait(
            # Post-generation hook creates related objects
        )

    title = factory.Faker('sentence', nb_words=5)
    slug = factory.Sequence(lambda n: f'essay-{n}')
    stage = 'drafting'
    draft = True
    date = factory.Faker('date_this_year')
    summary = factory.Faker('paragraph')
    body = factory.Faker('text', max_nb_chars=2000)
    tags = factory.LazyFunction(lambda: ['design'])

    @factory.post_generation
    def linked_sources(self, create, extracted, **kwargs):
        if not create:
            return
        if extracted:
            for source in extracted:
                SourceLinkFactory(
                    source=source,
                    content_type='essay',
                    content_slug=self.slug,
                    content_title=self.title,
                )


# Usage:
# EssayFactory(published=True)
# EssayFactory(in_research=True)
# EssayFactory.create_batch(5)
```

## Testing Business Logic

```python
from datetime import date, timedelta
from django.test import TestCase


class TestEssayWorkflow(TestCase):
    """Test publishing workflow rules, not that Django ORM works."""

    def test_published_essay_requires_summary(self):
        essay = EssayFactory(stage='drafting', summary='')
        with self.assertRaises(ValueError):
            essay.publish(editor=self.staff_user)

    def test_essay_can_publish_with_summary(self):
        essay = EssayFactory(stage='production', summary='A real summary.')
        essay.publish(editor=self.staff_user)
        self.assertEqual(essay.stage, 'published')
        self.assertFalse(essay.draft)

    def test_stage_transitions(self):
        essay = EssayFactory(stage='research')
        essay.advance_stage()
        self.assertEqual(essay.stage, 'drafting')

    def test_cannot_publish_from_research(self):
        essay = EssayFactory(stage='research')
        with self.assertRaises(ValueError):
            essay.publish(editor=self.staff_user)
```

## Testing Views

```python
from django.test import TestCase, Client
from django.urls import reverse


class TestEssayListView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(role='staff')
        self.client.force_login(self.user)

    def test_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('content:essay-list'))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_only_published(self):
        EssayFactory(published=True)
        EssayFactory(stage='drafting', draft=True)
        response = self.client.get(reverse('content:essay-list'))
        self.assertEqual(len(response.context['essays']), 1)

    def test_filter_by_tag(self):
        EssayFactory(tags=['design'])
        EssayFactory(tags=['systems'])
        response = self.client.get(
            reverse('content:essay-list'),
            {'tag': 'design'},
        )
        self.assertEqual(len(response.context['essays']), 1)
```

## Testing DRF APIs

```python
import pytest
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def authenticated_client(api_client, django_user_model):
    user = django_user_model.objects.create_user(
        username='testuser', password='testpass123'
    )
    api_client.force_authenticate(user=user)
    return api_client


@pytest.mark.django_db
class TestEssayAPI:
    """Test the essay API endpoints."""

    def test_list_requires_auth(self, api_client):
        url = reverse('content-api:essay-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_returns_paginated_results(self, authenticated_client):
        EssayFactory.create_batch(5, published=True)
        url = reverse('content-api:essay-list')
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'count' in response.data
        assert response.data['count'] == 5

    def test_list_uses_list_serializer(self, authenticated_client):
        """List endpoint should return lean fields, not full detail."""
        EssayFactory(published=True)
        response = authenticated_client.get(reverse('content-api:essay-list'))
        result = response.data['results'][0]
        # List serializer should NOT include nested objects
        assert 'sources' not in result
        assert 'field_notes' not in result
        # But should include summary fields
        assert 'title' in result
        assert 'stage' in result

    def test_detail_returns_full_representation(self, authenticated_client):
        essay = EssayFactory(published=True)
        url = reverse('content-api:essay-detail', kwargs={'slug': essay.slug})
        response = authenticated_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Detail serializer includes nested data
        assert 'sources' in response.data
        assert 'field_notes' in response.data

    def test_create_with_valid_data(self, authenticated_client):
        url = reverse('content-api:essay-list')
        data = {
            'title': 'Testing in Production',
            'slug': 'testing-in-production',
            'summary': 'Why testing matters.',
            'stage': 'drafting',
        }
        response = authenticated_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert Essay.objects.filter(slug='testing-in-production').exists()

    def test_create_with_invalid_data(self, authenticated_client):
        url = reverse('content-api:essay-list')
        response = authenticated_client.post(url, {}, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'title' in response.data  # required field error

    def test_filter_by_stage(self, authenticated_client):
        EssayFactory(published=True)
        EssayFactory(stage='drafting')
        url = reverse('content-api:essay-list')
        response = authenticated_client.get(url, {'stage': 'published'})
        assert response.data['count'] == 1

    def test_search(self, authenticated_client):
        EssayFactory(title='Design Systems Deep Dive', published=True)
        EssayFactory(title='Engineering Leadership', published=True)
        url = reverse('content-api:essay-list')
        response = authenticated_client.get(url, {'search': 'design'})
        assert response.data['count'] == 1

    def test_ordering(self, authenticated_client):
        EssayFactory(date=date(2025, 1, 1), published=True)
        EssayFactory(date=date(2025, 6, 1), published=True)
        url = reverse('content-api:essay-list')
        response = authenticated_client.get(url, {'ordering': '-date'})
        dates = [r['date'] for r in response.data['results']]
        assert dates == sorted(dates, reverse=True)
```

### Testing Permissions

```python
@pytest.mark.django_db
class TestEssayPermissions:
    def test_non_editor_cannot_publish(self, authenticated_client):
        essay = EssayFactory(stage='production')
        url = reverse('content-api:essay-detail', kwargs={'slug': essay.slug})
        response = authenticated_client.patch(
            url, {'stage': 'published'}, format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_editor_can_update(self, authenticated_client):
        # authenticated_client's user has editor permissions
        user = authenticated_client.handler._force_user
        essay = EssayFactory(stage='drafting')
        url = reverse('content-api:essay-detail', kwargs={'slug': essay.slug})
        response = authenticated_client.patch(
            url, {'summary': 'Updated summary'}, format='json'
        )
        assert response.status_code == status.HTTP_200_OK
```

## Testing HTMX Responses

HTMX endpoints return HTML partials, not full pages. Test that the response is a partial and that HTMX-specific headers are handled:

```python
class TestEssayListHTMX(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(role='staff')
        self.client.force_login(self.user)

    def test_htmx_request_returns_partial(self):
        """HTMX requests should return just the partial, not the full page."""
        EssayFactory.create_batch(3, published=True)
        response = self.client.get(
            reverse('content:essay-list'),
            HTTP_HX_REQUEST='true',  # simulate HTMX request header
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Partial should NOT contain <html>, <head>, or base template
        self.assertNotIn('<html', content)
        self.assertNotIn('<!DOCTYPE', content)
        # But should contain the list content
        self.assertIn('essay-list', content)

    def test_htmx_search_filters_results(self):
        EssayFactory(title='Design Systems Deep Dive', published=True)
        EssayFactory(title='Engineering Leadership', published=True)
        response = self.client.get(
            reverse('content:essay-list'),
            {'search': 'design'},
            HTTP_HX_REQUEST='true',
        )
        content = response.content.decode()
        self.assertIn('Design', content)
        self.assertNotIn('Leadership', content)

    def test_non_htmx_request_returns_full_page(self):
        """Regular requests should return the full page with base template."""
        response = self.client.get(reverse('content:essay-list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('<!DOCTYPE', content)
```

## Testing Management Commands

```python
from io import StringIO
from django.core.management import call_command


@pytest.mark.django_db
class TestSerializeContentCommand:
    def test_serialize_creates_markdown_files(self):
        """Test the serialize_content management command."""
        EssayFactory(published=True)
        out = StringIO()
        call_command('serialize_content', '--format=markdown', stdout=out)
        output = out.getvalue()
        assert 'Serialized' in output

    def test_serialize_handles_no_content(self):
        out = StringIO()
        call_command('serialize_content', '--format=markdown', '--dry-run', stdout=out)
        assert 'No content' in out.getvalue()

    def test_serialize_with_invalid_format(self):
        with pytest.raises(SystemExit):
            call_command('serialize_content', '--format=invalid')
```

## What to Test

| Layer | Test Thoroughly | Smoke Test Only |
|-------|----------------|-----------------|
| Models | Business logic, managers, constraints, validation | `__str__`, Meta options |
| Views | Permissions, redirects, context data, form handling | Template renders without error |
| API | Serializer validation, permissions, response shape, filtering | Read-only fields |
| Forms | Validation rules, clean methods, conditional fields | Field presence |
| Services | External API interaction (mocked), error handling | - |
| Commands | Core logic, edge cases, error handling | Help text |
| URLs | - | Reverse resolution works |
| Templates | - | No template syntax errors |

## Database Constraint Testing

```python
from django.db import IntegrityError


class TestModelConstraints(TestCase):
    def test_unique_source_link_per_role(self):
        source = SourceFactory()
        SourceLinkFactory(source=source, content_slug='essay-1', role='primary')
        with self.assertRaises(IntegrityError):
            SourceLinkFactory(source=source, content_slug='essay-1', role='primary')

    def test_non_negative_word_count(self):
        with self.assertRaises(IntegrityError):
            VideoSceneFactory(word_count=-100)
```

## Performance Testing Queries

```python
class TestQueryPerformance(TestCase):
    def test_list_view_query_count(self):
        # Create 20 essays
        EssayFactory.create_batch(20, published=True)

        with self.assertNumQueries(3):  # 1 count + 1 essays + 1 prefetch
            self.client.get(reverse('content:essay-list'))

    def test_api_list_query_count(self):
        """API list endpoint should use constant query count regardless of N."""
        EssayFactory.create_batch(20, published=True)
        client = APIClient()
        client.force_authenticate(UserFactory())

        with self.assertNumQueries(3):  # count + essays + sources
            client.get(reverse('content-api:essay-list'))
```
