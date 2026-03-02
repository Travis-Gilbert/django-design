# Django External API Integration Reference

When Django needs to communicate with external systems (GitHub, analytics services, content APIs, third-party platforms), isolate each integration behind a client class.

## Client Class Pattern

```python
# services/github_content.py
from django.conf import settings
from django.utils import timezone
import logging
import time

logger = logging.getLogger(__name__)


class GitHubContentClient:
    """Handles all communication with GitHub API for static site content."""

    def __init__(self):
        self.base_url = settings.GITHUB_API_URL
        self._token = settings.GITHUB_TOKEN
        self._repo = settings.GITHUB_CONTENT_REPO

    def _headers(self):
        return {
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/vnd.github.v3+json',
        }

    def get_file(self, path):
        """Fetch a file's content and SHA from the repository."""
        start = time.monotonic()
        try:
            response = self._request('GET', f'/repos/{self._repo}/contents/{path}')
            return response.json()
        finally:
            duration = time.monotonic() - start
            logger.info('GitHub get_file %s took %.2fs', path, duration)

    def commit_file(self, path, content, message='Update content'):
        """Create or update a file in the repository."""
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
def essay_detail(request, slug):
    essay = get_object_or_404(Essay, slug=slug)

    # External data is nice-to-have, not critical
    try:
        analytics_data = AnalyticsClient().get_page_stats(essay.slug)
    except ExternalServiceError:
        analytics_data = None
        logger.warning('Analytics lookup failed for %s', essay.slug)

    return render(request, 'content/essay_detail.html', {
        'essay': essay,
        'analytics_data': analytics_data,  # template handles None gracefully
    })
```

## Caching External Data

```python
from django.core.cache import cache


class OpenGraphClient:
    CACHE_TTL = 86400  # 24 hours

    def fetch_metadata(self, url):
        cache_key = f'opengraph:{url}'
        result = cache.get(cache_key)
        if result is not None:
            return result

        result = self._call_api(url)
        cache.set(cache_key, result, self.CACHE_TTL)
        return result
```

## Consuming Paginated APIs

Many external APIs return results in pages. Encapsulate pagination logic in the client so callers get a simple iterator:

```python
class ContentSyncClient:
    """Client for syncing content from an external CMS or feed."""

    def list_all_articles(self, filters=None):
        """Iterate over all pages of results transparently."""
        cursor = None
        while True:
            response = self._request('GET', '/articles', params={
                **(filters or {}),
                'cursor': cursor,
                'limit': 100,
            })
            data = response.json()
            yield from data['results']

            cursor = data.get('next_cursor')
            if not cursor:
                break

    def sync_content(self):
        """Sync external articles to local database."""
        for batch in self._iter_batches(self.list_all_articles(), size=50):
            essays = [
                Essay(
                    external_id=item['id'],
                    title=item['title'],
                    slug=item['slug'],
                )
                for item in batch
            ]
            Essay.objects.bulk_create(
                essays,
                update_conflicts=True,
                unique_fields=['external_id'],
                update_fields=['title', 'slug'],
            )

    @staticmethod
    def _iter_batches(iterable, size=50):
        from itertools import islice
        it = iter(iterable)
        while True:
            batch = list(islice(it, size))
            if not batch:
                break
            yield batch
```

**Pagination styles you will encounter:**
- **Cursor-based** (above): Use `next_cursor` from each response. Best for large datasets.
- **Offset-based**: Use `?offset=100&limit=50`. Watch for items shifting between pages during sync.
- **Page-number**: Use `?page=3`. Simple, but same shifting issue as offset.
- **Link header**: Follow `rel="next"` URL in HTTP Link header. Common in GitHub-style APIs.

## Receiving Webhooks

When external systems push data to your Django app via webhooks:

```python
# apps/integrations/views.py
import hashlib
import hmac
import json
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


@csrf_exempt
@require_POST
def github_webhook(request):
    """Receive push events from GitHub for deployment triggers."""
    # 1. Verify the webhook signature
    signature = request.headers.get('X-Hub-Signature-256', '')
    expected = 'sha256=' + hmac.new(
        settings.GITHUB_WEBHOOK_SECRET.encode(),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        logger.warning('Invalid webhook signature from %s', request.META.get('REMOTE_ADDR'))
        return HttpResponseBadRequest('Invalid signature')

    # 2. Parse the payload
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    # 3. Idempotency: check if we already processed this event
    delivery_id = request.headers.get('X-GitHub-Delivery', '')
    if WebhookEvent.objects.filter(event_id=delivery_id).exists():
        return HttpResponse('Already processed', status=200)

    # 4. Record the event and process asynchronously
    WebhookEvent.objects.create(
        event_id=delivery_id,
        event_type=request.headers.get('X-GitHub-Event', ''),
        payload=payload,
    )

    # Process in background (see background-tasks.md)
    from apps.integrations.tasks import process_github_webhook
    process_github_webhook.delay(delivery_id)

    return HttpResponse('OK', status=200)
```

### Webhook Best Practices

- **Always verify signatures.** Never trust unverified webhook payloads.
- **Return 200 quickly.** Process the payload asynchronously via a background task. External systems retry on non-200 responses, causing duplicate processing.
- **Implement idempotency.** Store processed event IDs to handle retries safely.
- **Log raw payloads.** Store the full payload in a `WebhookEvent` model for debugging failed processing.
- **Use `@csrf_exempt`** on webhook endpoints since external systems cannot provide CSRF tokens.

## File and Image Handling

### Image Processing with django-imagekit

```python
# pip install django-imagekit

from imagekit.models import ImageSpecField
from imagekit.processors import ResizeToFill, ResizeToFit


class Essay(TimeStampedModel):
    cover_image = models.ImageField(upload_to='essays/%Y/%m/')

    # Auto-generated variants
    cover_thumbnail = ImageSpecField(
        source='cover_image',
        processors=[ResizeToFill(300, 200)],
        format='JPEG',
        options={'quality': 85},
    )
    cover_large = ImageSpecField(
        source='cover_image',
        processors=[ResizeToFit(1200, 800)],
        format='JPEG',
        options={'quality': 90},
    )
```

### File Upload Validation

```python
from django.core.exceptions import ValidationError


def validate_file_size(value):
    max_size = 10 * 1024 * 1024  # 10 MB
    if value.size > max_size:
        raise ValidationError(f'File size must be under {max_size // (1024*1024)} MB.')


def validate_file_type(value):
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
    if hasattr(value.file, 'content_type') and value.file.content_type not in allowed_types:
        raise ValidationError('Only PDF, JPEG, and PNG files are allowed.')


class MediaAttachment(TimeStampedModel):
    file = models.FileField(
        upload_to='media/%Y/%m/',
        validators=[validate_file_size, validate_file_type],
    )
    media_type = models.CharField(max_length=50, choices=MEDIA_TYPE_CHOICES)
    essay = models.ForeignKey(Essay, on_delete=models.CASCADE, related_name='attachments')
```

## Integration Health Checks

Monitor external service availability:

```python
# services/health.py
import time


def check_external_services():
    """Run health checks on all external integrations."""
    results = {}

    for name, check_fn in [
        ('github', _check_github),
        ('analytics', _check_analytics),
        ('opengraph', _check_opengraph),
    ]:
        start = time.monotonic()
        try:
            check_fn()
            results[name] = {
                'status': 'healthy',
                'response_time_ms': round((time.monotonic() - start) * 1000),
            }
        except Exception as e:
            results[name] = {
                'status': 'unhealthy',
                'error': str(e),
                'response_time_ms': round((time.monotonic() - start) * 1000),
            }

    return results


def _check_github():
    client = GitHubContentClient()
    client.get_file('README.md')


# Expose as a Django view
from django.http import JsonResponse

def health_check(request):
    results = check_external_services()
    all_healthy = all(r['status'] == 'healthy' for r in results.values())
    return JsonResponse(results, status=200 if all_healthy else 503)
```

## Testing External Integrations

Mock external calls in tests to avoid hitting real APIs:

```python
from unittest.mock import patch


class TestEssayWithAnalytics(TestCase):
    @patch('apps.content.services.AnalyticsClient.get_page_stats')
    def test_detail_with_analytics(self, mock_stats):
        mock_stats.return_value = {'page_views': 4500, 'avg_time': 180}
        response = self.client.get(f'/essays/{self.essay.slug}/')
        self.assertContains(response, '4,500')

    @patch('apps.content.services.AnalyticsClient.get_page_stats')
    def test_detail_without_analytics(self, mock_stats):
        mock_stats.side_effect = ExternalServiceError('timeout')
        response = self.client.get(f'/essays/{self.essay.slug}/')
        self.assertEqual(response.status_code, 200)  # page still loads
```

### Using responses for HTTP Mocking

```python
# pip install responses
import responses


class TestOpenGraphClient(TestCase):
    @responses.activate
    def test_fetch_metadata_success(self):
        responses.add(
            responses.GET,
            'https://api.example.com/metadata',
            json={'title': 'Great Article', 'image': 'https://example.com/img.jpg'},
            status=200,
        )
        client = OpenGraphClient()
        result = client.fetch_metadata('https://example.com/great-article')
        assert result['title'] == 'Great Article'

    @responses.activate
    def test_fetch_metadata_retries_on_500(self):
        responses.add(responses.GET, 'https://api.example.com/metadata', status=500)
        responses.add(responses.GET, 'https://api.example.com/metadata', status=500)
        responses.add(
            responses.GET,
            'https://api.example.com/metadata',
            json={'title': 'Great Article', 'image': 'https://example.com/img.jpg'},
            status=200,
        )
        client = OpenGraphClient()
        result = client.fetch_metadata('https://example.com/great-article')
        assert len(responses.calls) == 3
```
