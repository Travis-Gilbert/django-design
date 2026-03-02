# Django External API Integration Reference

When Django needs to communicate with external systems (FileMaker, Salesforce, legacy databases, third-party APIs), isolate each integration behind a client class.

## Client Class Pattern

```python
# services/filemaker.py
from django.conf import settings
from django.utils import timezone
import logging
import time

logger = logging.getLogger(__name__)


class FileMakerClient:
    """Handles all communication with FileMaker Data API."""

    def __init__(self):
        self.base_url = settings.FILEMAKER_HOST
        self._token = None
        self._token_expires = None

    def _get_token(self):
        """Get or refresh session token."""
        if self._token and self._token_expires > timezone.now():
            return self._token
        # ... token refresh logic

    def find_records(self, layout, query):
        """Execute a find request against a FileMaker layout."""
        start = time.monotonic()
        try:
            response = self._request('POST', f'/layouts/{layout}/_find', json=query)
            return response.json()
        finally:
            duration = time.monotonic() - start
            logger.info('FileMaker find on %s took %.2fs', layout, duration)

    def update_record(self, layout, record_id, field_data):
        """Update a single record."""
        # ... implementation
```

## Integration Principles

1. **One client class per external system**, living in `services/` or a dedicated `integrations/` directory
2. **Handle authentication internally** so callers never think about tokens
3. **Retry with backoff** for transient failures
4. **Log every external call** at the INFO level minimum, with timing
5. **Cache aggressively** where the data does not change frequently
6. **Never let external failures crash views.** Wrap calls in try/except and degrade gracefully

## Retry Pattern

```python
import time
from functools import wraps


def retry_with_backoff(max_retries=3, base_delay=1.0, exceptions=(Exception,)):
    """Decorator for retrying external API calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        'Retry %d/%d for %s after error: %s (waiting %.1fs)',
                        attempt + 1, max_retries, func.__name__, e, delay,
                    )
                    time.sleep(delay)
        return wrapper
    return decorator
```

## Graceful Degradation in Views

```python
def property_detail(request, property_id):
    property = get_object_or_404(Property, pk=property_id)

    # External data is nice-to-have, not critical
    try:
        tax_data = TaxAssessorClient().get_assessment(property.parcel_id)
    except ExternalServiceError:
        tax_data = None
        logger.warning('Tax assessor lookup failed for %s', property.parcel_id)

    return render(request, 'properties/detail.html', {
        'property': property,
        'tax_data': tax_data,  # template handles None gracefully
    })
```

## Caching External Data

```python
from django.core.cache import cache


class GeocodingClient:
    CACHE_TTL = 86400  # 24 hours

    def geocode(self, address):
        cache_key = f'geocode:{address}'
        result = cache.get(cache_key)
        if result is not None:
            return result

        result = self._call_api(address)
        cache.set(cache_key, result, self.CACHE_TTL)
        return result
```

## Testing External Integrations

Mock external calls in tests to avoid hitting real APIs:

```python
from unittest.mock import patch


class TestPropertyWithTaxData(TestCase):
    @patch('apps.properties.services.TaxAssessorClient.get_assessment')
    def test_detail_with_tax_data(self, mock_assessment):
        mock_assessment.return_value = {'assessed_value': 45000}
        response = self.client.get(f'/properties/{self.property.pk}/')
        self.assertContains(response, '45,000')

    @patch('apps.properties.services.TaxAssessorClient.get_assessment')
    def test_detail_without_tax_data(self, mock_assessment):
        mock_assessment.side_effect = ExternalServiceError('timeout')
        response = self.client.get(f'/properties/{self.property.pk}/')
        self.assertEqual(response.status_code, 200)  # page still loads
```
