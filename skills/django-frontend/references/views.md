# Django Views and URL Patterns Reference

This reference covers template-based views (function-based and class-based) and URL configuration. For REST API views with DRF, see api.md.

## Function-Based vs Class-Based Views

Both are tools with different strengths. This is not a religious debate.

**Use function-based views when:**
- The logic is linear and specific to one endpoint
- You're handling a form submission with custom validation flow
- The view does something unusual that doesn't fit a generic pattern
- You want maximum readability for someone new to the codebase

**Use class-based views when:**
- You're building standard CRUD operations
- You need to share behavior across multiple views (mixins)
- Django's generic views (ListView, DetailView, CreateView) match your use case

**Use DRF ViewSets when:**
- You're building a REST API - see api.md for patterns

```python
# Function-based: clear, linear, easy to follow
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods


@login_required
@require_http_methods(["GET"])
def essay_source_summary(request, slug):
    """Return source summary for a single essay."""
    essay = get_object_or_404(
        Essay.objects.with_source_stats(),
        slug=slug,
    )

    if not request.user.has_perm('content.view_essay'):
        raise PermissionDenied

    return render(request, 'content/source_summary.html', {
        'essay': essay,
        'source_count': essay.source_count,
        'stage': essay.get_stage_display(),
        'is_published': essay.stage == 'published',
    })


# Class-based: leverages Django's generic patterns
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


class EssayListView(LoginRequiredMixin, ListView):
    model = Essay
    template_name = 'content/essay_list.html'
    context_object_name = 'essays'
    paginate_by = 25

    def get_queryset(self):
        qs = Essay.objects.published().select_related('video_project')

        tag = self.request.GET.get('tag')
        if tag:
            qs = qs.by_tag(tag)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['tags'] = Essay.objects.published().values_list(
            'tags', flat=True
        ).distinct()
        return context
```

### Common CBV Patterns

```python
class EssayCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Essay
    form_class = EssayForm
    template_name = 'content/essay_edit.html'
    permission_required = 'content.add_essay'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('content:essay-detail', kwargs={'slug': self.object.slug})


class EssayUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Essay
    form_class = EssayForm
    template_name = 'content/essay_edit.html'
    permission_required = 'content.change_essay'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        """Only allow editing essays in draft stages."""
        return super().get_queryset().filter(stage__in=['research', 'drafting', 'production'])
```

**When NOT to use generic CBVs:**
- If you're overriding 3+ methods, a function-based view is likely clearer.
- If the view orchestrates multiple forms or models, a plain function gives you more control.
- If you're returning JSON from a template view, consider whether it should be an API endpoint (see api.md).

## Form Handling in Views

See forms.md for form definitions. Here is the view-side pattern:

```python
@login_required
def essay_edit(request, slug):
    essay = get_object_or_404(Essay, slug=slug)

    if request.method == 'POST':
        form = EssayForm(request.POST, instance=essay)
        source_formset = SourceFormSet(request.POST, instance=essay)
        if form.is_valid() and source_formset.is_valid():
            form.save()
            source_formset.save()
            messages.success(request, 'Essay updated successfully.')
            return redirect('content:essay-detail', slug=essay.slug)
    else:
        form = EssayForm(instance=essay)
        source_formset = SourceFormSet(instance=essay)

    return render(request, 'content/essay_edit.html', {
        'form': form,
        'source_formset': source_formset,
        'essay': essay,
    })
```

**Key pattern:** Always return the form with errors on POST failure. Never redirect after a failed `is_valid()` - the user loses their input and error messages.

## URL Patterns

```python
# project_name/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('apps.content.api_urls', namespace='content-api')),
    path('', include('apps.content.urls', namespace='content')),
]


# apps/content/urls.py
from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('essays/', views.EssayListView.as_view(), name='essay-list'),
    path('essays/<slug:slug>/', views.EssayDetailView.as_view(), name='essay-detail'),
    path('essays/new/', views.EssayCreateView.as_view(), name='essay-create'),
    path('essays/<slug:slug>/edit/', views.EssayUpdateView.as_view(), name='essay-edit'),
    path('essays/<slug:slug>/sources/', views.essay_source_summary, name='essay-sources'),
    path('field-notes/', views.FieldNoteListView.as_view(), name='fieldnote-list'),
    path('export/', views.export_essays, name='export'),
]
```

**URL conventions:**
- Always set `app_name` for URL namespacing. This prevents collisions.
- Use `include()` to keep each app's URLs in its own file.
- Name every URL. Templates use `{% url 'content:essay-list' %}`, code uses `reverse('content:essay-list')`.
- Keep API URLs in a separate file (`api_urls.py`) from template-view URLs (`urls.py`). See api.md for router configuration.
- Use `<slug:slug>` type converters for content models. They validate at the URL level so your view never receives an invalid slug.

## Pagination

Always paginate list views. Unbounded querysets are the most common performance problem.

```python
# For template-based views, use Django's built-in Paginator
from django.core.paginator import Paginator


def essay_list(request):
    essays = Essay.objects.published().select_related('video_project')

    # Apply search/filter form
    form = EssaySearchForm(request.GET)
    if form.is_valid():
        essays = form.filter_queryset(essays)

    paginator = Paginator(essays, 25)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'content/essay_list.html', {
        'page': page,
        'form': form,
    })
```

For DRF pagination options (PageNumber, LimitOffset, Cursor), see api.md.

## Middleware

Custom middleware should be rare and focused. If it's doing heavy lifting, it probably belongs in a view decorator or a mixin instead.

```python
# apps/core/middleware.py
import time
import logging

logger = logging.getLogger('django.request')


class RequestTimingMiddleware:
    """Log request duration for performance monitoring."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration = time.monotonic() - start

        if duration > 1.0:  # log slow requests
            logger.warning(
                'Slow request: %s %s took %.2fs',
                request.method, request.path, duration,
            )

        response['X-Request-Duration'] = f'{duration:.3f}'
        return response


class CurrentUserMiddleware:
    """Make the current user available to model methods
    without passing request around everywhere.

    Use sparingly. This uses thread-local storage which
    doesn't work with async views.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.core.context import set_current_user
        set_current_user(request.user)
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)
```

## File Upload Handling

```python
from django.core.validators import FileExtensionValidator


class VideoDeliverable(TimeStampedModel):
    video = models.ForeignKey(VideoProject, on_delete=models.CASCADE, related_name='deliverables')
    deliverable_type = models.CharField(max_length=50)
    file = models.FileField(
        upload_to='deliverables/%Y/%m/',
        validators=[
            FileExtensionValidator(allowed_extensions=['mp4', 'mov', 'pdf', 'jpg', 'png']),
        ],
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    file_size = models.PositiveIntegerField(editable=False)

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
        super().save(*args, **kwargs)


# In the view or serializer, validate file size
def validate_file(file):
    max_size = 10 * 1024 * 1024  # 10MB
    if file.size > max_size:
        raise ValidationError(f'File size must be under 10MB. Got {file.size / 1024 / 1024:.1f}MB.')
```

For production file storage, use `django-storages` with S3 or equivalent:

```python
# settings/production.py
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    },
}
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')
AWS_DEFAULT_ACL = 'private'  # never default to public
```

## Error Handling

```python
# For template views, use Django's error handling
from django.http import Http404
from django.core.exceptions import PermissionDenied


def essay_detail(request, slug):
    try:
        essay = Essay.objects.select_related('video_project').get(slug=slug)
    except Essay.DoesNotExist:
        raise Http404('Essay not found')

    if not request.user.has_perm('content.view_essay'):
        raise PermissionDenied

    return render(request, 'content/essay_detail.html', {'essay': essay})


# Custom error views
# urls.py
handler404 = 'apps.core.views.custom_404'
handler500 = 'apps.core.views.custom_500'
```

For API error handling (DRF exceptions, custom handlers), see api.md.

**Error handling principles:**
- Use `get_object_or_404()` as a shortcut when you just need to fetch or 404.
- Raise `PermissionDenied` instead of returning a manual 403 response.
- Log server errors (500s) with full context. Don't log client errors (400s) at ERROR level - those are expected.
- Never expose internal error details (tracebacks, SQL queries) in production responses.

## Anti-Patterns

- **Putting business logic in views.** Views should orchestrate (get data, validate, save, redirect), not compute. If your view has complex conditionals, move that logic to the model or a service layer.
- **Forgetting `select_related` / `prefetch_related`.** Every `get_queryset()` should think about what related objects the template needs. The Django Debug Toolbar will show you N+1 queries.
- **No pagination on list views.** Every list endpoint needs pagination. A view that renders 50,000 objects will time out or crash the browser.
- **Redirecting after form validation failure.** If `form.is_valid()` returns False, render the same template with the form. Redirecting loses the user's input and error messages.
- **Manual permission checks instead of mixins.** Use `LoginRequiredMixin` and `PermissionRequiredMixin` on CBVs, or `@login_required` and `@permission_required` decorators on FBVs. Don't write `if not request.user.is_authenticated` in every view.
