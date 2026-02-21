# Django Testing Strategy Reference

## Core Principle

Prioritize testing business logic, not Django machinery. Models and domain logic get thorough tests. Template rendering and URL routing get smoke tests. Do not test that the ORM works.

## Test Organization

```
apps/your_app/tests/
    __init__.py
    test_models.py      # model methods, managers, constraints
    test_views.py       # request/response, permissions, redirects
    test_services.py    # service layer business logic
    test_forms.py       # form validation (if using Django forms)
    test_serializers.py # serializer validation (if using DRF)
    factories.py        # factory_boy factories
    conftest.py         # pytest fixtures (if using pytest)
```

## factory_boy Over Fixtures

Use `factory_boy` for test data, not JSON fixtures. Factories compose better and make tests self-documenting.

```python
# tests/factories.py
import factory
from apps.properties.models import Property, Buyer


class BuyerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Buyer

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.LazyAttribute(
        lambda obj: f'{obj.first_name.lower()}.{obj.last_name.lower()}@example.com'
    )


class PropertyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Property

    address = factory.Faker('street_address')
    parcel_id = factory.Sequence(lambda n: f'{n:02d}-01-100-{n:03d}')
    program = 'featured_homes'
    status = 'pending'
    buyer = factory.SubFactory(BuyerFactory)
    purchase_date = factory.Faker('date_this_year')
```

## Testing Business Logic

```python
from datetime import date, timedelta
from django.test import TestCase


class TestPropertyCompliance(TestCase):
    """Test compliance rules, not that Django ORM works."""

    def test_property_overdue_after_deadline(self):
        prop = PropertyFactory(
            purchase_date=date.today() - timedelta(days=181),
            program='featured_homes',
        )
        self.assertTrue(prop.is_overdue)

    def test_property_not_overdue_within_deadline(self):
        prop = PropertyFactory(
            purchase_date=date.today() - timedelta(days=90),
        )
        self.assertFalse(prop.is_overdue)

    def test_compliance_status_transitions(self):
        prop = PropertyFactory(status='pending_review')
        prop.approve(reviewer=self.staff_user)
        self.assertEqual(prop.status, 'approved')
        self.assertEqual(prop.reviewed_by, self.staff_user)
        self.assertIsNotNone(prop.reviewed_at)

    def test_cannot_approve_already_approved(self):
        prop = PropertyFactory(status='approved')
        with self.assertRaises(ValueError):
            prop.approve(reviewer=self.staff_user)
```

## Testing Views

```python
from django.test import TestCase, Client
from django.urls import reverse


class TestPropertyListView(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(role='staff')
        self.client.force_login(self.user)

    def test_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse('properties:list'))
        self.assertEqual(response.status_code, 302)

    def test_list_shows_only_active(self):
        PropertyFactory(status='active')
        PropertyFactory(status='deleted')
        response = self.client.get(reverse('properties:list'))
        self.assertEqual(len(response.context['properties']), 1)

    def test_filter_by_program(self):
        PropertyFactory(program='featured_homes')
        PropertyFactory(program='ready_for_rehab')
        response = self.client.get(
            reverse('properties:list'),
            {'program': 'featured_homes'},
        )
        self.assertEqual(len(response.context['properties']), 1)
```

## Testing with pytest-django

```python
import pytest
from .factories import PropertyFactory


@pytest.mark.django_db
class TestPropertyModel:
    def test_overdue_property(self):
        prop = PropertyFactory(
            purchase_date=date.today() - timedelta(days=200),
        )
        assert prop.is_overdue is True

    def test_reference_number_format(self):
        prop = PropertyFactory()
        prop.generate_reference_number()
        assert prop.reference_number.startswith('GCLBA-')
        assert len(prop.reference_number) == 14


@pytest.fixture
def staff_client(db):
    user = UserFactory(role='staff')
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_property_detail(staff_client):
    prop = PropertyFactory()
    response = staff_client.get(f'/properties/{prop.pk}/')
    assert response.status_code == 200
    assert prop.address in response.content.decode()
```

## What to Test

| Layer | Test Thoroughly | Smoke Test Only |
|-------|----------------|-----------------|
| Models | Business logic, managers, constraints, validation | `__str__`, Meta options |
| Views | Permissions, redirects, context data, form handling | Template renders without error |
| Forms | Validation rules, clean methods, conditional fields | Field presence |
| Serializers | Validation, computed fields, nested output | Read-only fields |
| Services | External API interaction (mocked), error handling | — |
| URLs | — | Reverse resolution works |
| Templates | — | No template syntax errors |

## Database Constraint Testing

```python
from django.db import IntegrityError


class TestModelConstraints(TestCase):
    def test_unique_active_review(self):
        prop = PropertyFactory()
        ReviewFactory(property=prop, review_type='compliance', status='active')
        with self.assertRaises(IntegrityError):
            ReviewFactory(property=prop, review_type='compliance', status='active')

    def test_positive_purchase_price(self):
        with self.assertRaises(IntegrityError):
            PropertyFactory(purchase_price=-100)
```

## Performance Testing Queries

```python
from django.test.utils import override_settings


class TestQueryPerformance(TestCase):
    def test_list_view_query_count(self):
        # Create 20 properties with related objects
        for _ in range(20):
            PropertyFactory()

        with self.assertNumQueries(3):  # 1 count + 1 properties + 1 buyers
            self.client.get(reverse('properties:list'))
```
