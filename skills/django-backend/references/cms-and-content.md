# Django CMS and Content Management Reference

## Content Architecture

Every application eventually needs some form of user-editable content. On one end: a single `TextField` with raw HTML. On the other: a full CMS with page trees, versioned plugins, and editorial workflows. Most projects land in the middle.

This reference covers the spectrum, from flat content models through structured page hierarchies, drawing patterns from django-cms and real-world content systems.

## Flat Content Models

A model with title, body, and metadata. Good for blogs, news, FAQ entries, and any content type with uniform structure.

```python
from django.db import models
from django.utils.text import slugify
from apps.core.models import TimeStampedModel


class PublishableModel(TimeStampedModel):
    """Abstract base for content that goes through a publish workflow."""

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        REVIEW = 'review', 'In Review'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        'core.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='%(class)s_published',
    )

    class Meta:
        abstract = True

    def publish(self, user):
        if self.status == self.Status.PUBLISHED:
            return
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        self.published_by = user
        self.save(update_fields=['status', 'published_at', 'published_by', 'updated_at'])

    def unpublish(self):
        self.status = self.Status.DRAFT
        self.published_at = None
        self.save(update_fields=['status', 'published_at', 'updated_at'])


class Article(PublishableModel):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    summary = models.TextField(blank=True)
    body = models.TextField()
    author = models.ForeignKey('core.User', on_delete=models.PROTECT)
    featured_image = models.ImageField(upload_to='articles/%Y/%m/', blank=True)
    category = models.ForeignKey('Category', on_delete=models.PROTECT)
    tags = models.ManyToManyField('Tag', blank=True)

    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['status', '-published_at']),
            models.Index(fields=['category', 'status']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
```

### Content Managers

Encode common content queries into the manager so views stay thin.

```python
class ArticleQuerySet(models.QuerySet):
    def published(self):
        return self.filter(
            status=Article.Status.PUBLISHED,
            published_at__lte=timezone.now(),
        )

    def by_category(self, category_slug):
        return self.filter(category__slug=category_slug)

    def recent(self, count=10):
        return self.published().order_by('-published_at')[:count]

    def with_related(self):
        return self.select_related('author', 'category').prefetch_related('tags')


class ArticleManager(models.Manager):
    def get_queryset(self):
        return ArticleQuerySet(self.model, using=self._db)

    def published(self):
        return self.get_queryset().published()
```

## Page Trees and Hierarchical Content

When content needs parent-child relationships (site navigation, documentation trees, nested pages), use a tree structure.

### Using django-treebeard

```python
# pip install django-treebeard

from treebeard.mp_tree import MP_Node


class Page(MP_Node):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    template = models.CharField(
        max_length=100,
        choices=[
            ('pages/default.html', 'Default'),
            ('pages/landing.html', 'Landing Page'),
            ('pages/sidebar.html', 'With Sidebar'),
        ],
        default='pages/default.html',
    )
    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    changed_at = models.DateTimeField(auto_now=True)

    node_order_by = ['title']

    class Meta:
        indexes = [models.Index(fields=['slug', 'depth'])]

    def get_absolute_url(self):
        ancestors = self.get_ancestors()
        parts = [a.slug for a in ancestors] + [self.slug]
        return '/' + '/'.join(parts) + '/'

    @classmethod
    def get_published_tree(cls):
        return cls.objects.filter(is_published=True).order_by('path')
```

**Tree library comparison:**
- **django-treebeard** (MP_Node): Materialized path. Fast reads, consistent writes. Used by django-cms.
- **django-mptt**: Modified Preorder Tree Traversal. Fast reads, but tree corruption can happen on concurrent writes.
- **django-treebeard** (AL_Node): Adjacency list. Simple, but slow for deep queries. Fine for 2-3 levels.

### URL Resolution for Page Trees

```python
def page_detail(request, path=''):
    slugs = [s for s in path.split('/') if s]

    if not slugs:
        try:
            page = Page.get_first_root_node()
        except Page.DoesNotExist:
            raise Http404
    else:
        page = None
        for i, slug in enumerate(slugs):
            if i == 0:
                pages = Page.get_root_nodes().filter(slug=slug)
            else:
                pages = page.get_children().filter(slug=slug)
            page = pages.first()
            if page is None:
                raise Http404

    if not page.is_published and not request.user.is_staff:
        raise Http404

    return render(request, page.template, {
        'page': page,
        'breadcrumbs': page.get_ancestors(),
        'children': page.get_children().filter(is_published=True),
    })


# urls.py
urlpatterns = [
    path('pages/', page_detail, name='page-root'),
    path('pages/<path:path>/', page_detail, name='page-detail'),
]
```

## Placeholder and Plugin Architecture

Instead of a single body field, pages contain "placeholders" (named content regions), each holding an ordered list of "plugins" (typed content blocks). This is the pattern that powers django-cms.

### Building Your Own Plugin System

You do not need django-cms for this pattern. Here is a minimal implementation:

```python
class Placeholder(models.Model):
    slot = models.CharField(max_length=255, db_index=True)
    page = models.ForeignKey('Page', on_delete=models.CASCADE, related_name='placeholders')

    class Meta:
        unique_together = ['slot', 'page']

    def get_plugins(self):
        return self.plugins.order_by('position')


class ContentPlugin(TimeStampedModel):
    """Base class for all content plugins."""
    placeholder = models.ForeignKey(Placeholder, on_delete=models.CASCADE, related_name='plugins')
    position = models.PositiveIntegerField(default=0)
    plugin_type = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ['position']

    def get_plugin_instance(self):
        return getattr(self, self.plugin_type.lower(), self)


# Concrete plugin types
class TextPlugin(ContentPlugin):
    body = models.TextField()

    def save(self, *args, **kwargs):
        self.plugin_type = 'textplugin'
        super().save(*args, **kwargs)


class ImagePlugin(ContentPlugin):
    image = models.ImageField(upload_to='plugins/images/%Y/%m/')
    caption = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        self.plugin_type = 'imageplugin'
        super().save(*args, **kwargs)


class CallToActionPlugin(ContentPlugin):
    heading = models.CharField(max_length=255)
    text = models.TextField()
    button_text = models.CharField(max_length=100)
    button_url = models.URLField()

    def save(self, *args, **kwargs):
        self.plugin_type = 'calltoactionplugin'
        super().save(*args, **kwargs)
```

### Rendering Plugins in Templates

```python
# templatetags/content_tags.py
from django import template

register = template.Library()

PLUGIN_TEMPLATES = {
    'textplugin': 'plugins/text.html',
    'imageplugin': 'plugins/image.html',
    'calltoactionplugin': 'plugins/cta.html',
}


@register.inclusion_tag('plugins/placeholder.html', takes_context=True)
def render_placeholder(context, page, slot):
    try:
        placeholder = page.placeholders.get(slot=slot)
        plugins = placeholder.get_plugins()
    except Placeholder.DoesNotExist:
        plugins = []

    rendered = []
    for plugin in plugins:
        instance = plugin.get_plugin_instance()
        tmpl = PLUGIN_TEMPLATES.get(plugin.plugin_type, 'plugins/default.html')
        rendered.append({'instance': instance, 'template': tmpl})
    return {'plugins': rendered}
```

```html
{# templates/plugins/placeholder.html #}
{% for plugin in plugins %}
    {% include plugin.template with plugin=plugin.instance %}
{% endfor %}

{# templates/pages/default.html #}
{% load content_tags %}
{% extends 'base.html' %}

{% block content %}
    <header>{% render_placeholder page "hero" %}</header>
    <main>{% render_placeholder page "content" %}</main>
    <aside>{% render_placeholder page "sidebar" %}</aside>
{% endblock %}
```

## Content Versioning

For applications that need editorial review, audit trails, or undo capability.

### Simple Version History

```python
class ArticleVersion(TimeStampedModel):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    body = models.TextField()
    created_by = models.ForeignKey('core.User', on_delete=models.PROTECT)
    change_summary = models.CharField(max_length=500, blank=True)

    class Meta:
        unique_together = ['article', 'version_number']
        ordering = ['-version_number']

    @classmethod
    def create_from_article(cls, article, user, summary=''):
        last = article.versions.order_by('-version_number').first()
        next_number = (last.version_number + 1) if last else 1
        return cls.objects.create(
            article=article,
            version_number=next_number,
            title=article.title,
            body=article.body,
            created_by=user,
            change_summary=summary,
        )
```

### Draft/Live Content Pattern

Separate "draft" content (what editors see) from "live" content (what the public sees). This is the pattern django-cms uses.

```python
class PageContent(TimeStampedModel):
    page = models.ForeignKey('Page', on_delete=models.CASCADE, related_name='content_set')
    language = models.CharField(max_length=10, default='en')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    is_draft = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['page', 'language', 'is_draft'],
                name='unique_page_content_per_language_version',
            ),
        ]

    @classmethod
    def publish(cls, page, language, user):
        draft = cls.objects.get(page=page, language=language, is_draft=True)
        live, created = cls.objects.update_or_create(
            page=page,
            language=language,
            is_draft=False,
            defaults={'title': draft.title, 'slug': draft.slug},
        )
        return live
```

## django-cms Integration

When a project needs a full CMS with page trees, placeholders, plugins, permissions, multi-language support, and editorial workflows out of the box.

### Setup

```python
# pip install django-cms

INSTALLED_APPS = ['cms', 'menus', 'treebeard', 'sekizai', ...]

CMS_TEMPLATES = [
    ('pages/default.html', 'Default'),
    ('pages/landing.html', 'Landing Page'),
    ('pages/sidebar.html', 'With Sidebar'),
]

CMS_PLACEHOLDER_CONF = {
    'content': {
        'plugins': ['TextPlugin', 'ImagePlugin', 'VideoPlugin'],
        'limits': {'TextPlugin': 10},
    },
    'sidebar': {
        'plugins': ['TextPlugin', 'CallToActionPlugin'],
    },
}
```

### Custom CMS Plugins

Plugins bridge CMS pages with your application models. Each plugin has a model (storing data) and a plugin class (controlling rendering). Here are content-site plugins that surface essays and research within CMS-managed pages:

```python
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.models.pluginmodel import CMSPlugin


# --- Essay Highlight: feature an essay on any CMS page ---

class EssayHighlightModel(CMSPlugin):
    essay = models.ForeignKey('content.Essay', on_delete=models.CASCADE)
    show_word_count = models.BooleanField(default=True)
    show_stage = models.BooleanField(default=True)

    def __str__(self):
        return f'Essay: {self.essay.title}'


@plugin_pool.register_plugin
class EssayHighlightPlugin(CMSPluginBase):
    model = EssayHighlightModel
    name = 'Essay Highlight'
    render_template = 'plugins/essay_highlight.html'
    cache = True

    def render(self, context, instance, placeholder):
        context.update({
            'essay': instance.essay,
            'show_word_count': instance.show_word_count,
            'show_stage': instance.show_stage,
        })
        return context


# --- Source List: display research sources by slug reference ---
# Sources live in a separate Research API service. The plugin stores
# content_slug strings (not ForeignKeys) to bridge the two services.
# See models.md for the SourceLink cross-service pattern.

class SourceListModel(CMSPlugin):
    content_slug = models.SlugField(
        max_length=255,
        help_text='Slug of the content item to show sources for (cross-service reference)',
    )
    max_sources = models.PositiveIntegerField(default=5)

    def __str__(self):
        return f'Sources for: {self.content_slug}'


@plugin_pool.register_plugin
class SourceListPlugin(CMSPluginBase):
    model = SourceListModel
    name = 'Source List'
    render_template = 'plugins/source_list.html'
    cache = False  # depends on external Research API data

    def render(self, context, instance, placeholder):
        from apps.content.models import SourceLink
        source_links = (
            SourceLink.objects
            .filter(content_slug=instance.content_slug)
            .order_by('-created_at')[:instance.max_sources]
        )
        context.update({
            'source_links': source_links,
            'content_slug': instance.content_slug,
        })
        return context


# --- Thread Timeline: visualize a research thread's progression ---

class ThreadTimelineModel(CMSPlugin):
    thread_slug = models.SlugField(
        max_length=255,
        help_text='Slug of the research thread (cross-service reference)',
    )
    show_entries = models.BooleanField(default=True)

    def __str__(self):
        return f'Thread: {self.thread_slug}'


@plugin_pool.register_plugin
class ThreadTimelinePlugin(CMSPluginBase):
    model = ThreadTimelineModel
    name = 'Thread Timeline'
    render_template = 'plugins/thread_timeline.html'
    cache = False

    def render(self, context, instance, placeholder):
        context.update({
            'thread_slug': instance.thread_slug,
            'show_entries': instance.show_entries,
        })
        return context
```

The SourceListPlugin and ThreadTimelinePlugin use slug strings to reference data in the Research API service. This follows the cross-service architecture where two Django services reference each other by slug, not by ForeignKey. See models.md for the SourceLink pattern.

### Key django-cms Concepts

**Pages** are tree nodes (using treebeard). They define structure and URL hierarchy but hold no content directly.

**PageContent** stores translatable content (title, slug, meta description) for each page in each language.

**Placeholders** are named slots defined in templates using `{% placeholder "content" %}`. They are content regions where plugins live.

**Plugins** are the actual content blocks: a model (storing data) paired with a plugin class (controlling rendering). The plugin model inherits from `CMSPlugin`, providing tree structure (plugins can nest), placeholder reference, and position ordering.

**Permissions** control who can edit which pages, with page-level, placeholder-level, and plugin-type restrictions.

### Apphooks: Connecting Django Apps to CMS Pages

Apphooks let you attach a Django app's URL configuration to a CMS page. The page provides the URL prefix and navigation position; the app provides the views.

```python
# apps/content/cms_apps.py
from cms.app_base import CMSApp
from cms.apphook_pool import apphook_pool


@apphook_pool.register
class ContentApphook(CMSApp):
    app_name = 'content'
    name = 'Content Publishing'

    def get_urls(self, page=None, language=None, **kwargs):
        return ['apps.content.urls']
```

```python
# apps/content/urls.py
from django.urls import path
from . import views

app_name = 'content'

urlpatterns = [
    path('', views.essay_list, name='essay-list'),
    path('<slug:slug>/', views.essay_detail, name='essay-detail'),
    path('stage/<str:stage>/', views.essays_by_stage, name='essays-by-stage'),
]
```

When a CMS page uses the ContentApphook, visiting `/writing/` shows `essay_list`, and `/writing/my-essay-slug/` shows `essay_detail`. The `/writing/` prefix comes from the page's position in the CMS tree, not from the app's URL configuration. This decouples content structure from URL routing.

### Placeholder Strategy

Name placeholders by their structural role, not their content. This keeps templates reusable across page types:

```html
{# Good: structural slot names #}
{% placeholder "hero" %}
{% placeholder "main_content" %}
{% placeholder "sidebar" %}
{% placeholder "footer_cta" %}

{# Bad: content-specific slot names #}
{% placeholder "essay_list" %}
{% placeholder "source_references" %}
```

Configure which plugins are allowed in each placeholder. This prevents editors from placing chart widgets in the sidebar or call-to-action blocks in the hero:

```python
CMS_PLACEHOLDER_CONF = {
    'hero': {
        'plugins': ['TextPlugin', 'ImagePlugin', 'EssayHighlightPlugin'],
        'limits': {'EssayHighlightPlugin': 1},
        'name': 'Hero Section',
    },
    'main_content': {
        'plugins': [
            'TextPlugin', 'ImagePlugin', 'EssayHighlightPlugin',
            'SourceListPlugin', 'ThreadTimelinePlugin',
        ],
        'name': 'Main Content',
    },
    'sidebar': {
        'plugins': ['TextPlugin', 'SourceListPlugin'],
        'name': 'Sidebar',
    },
}
```

### Headless CMS: API Endpoints for CMS Content

When CMS content needs to be consumed by a frontend framework, static site generator, or mobile app, expose it through API endpoints. This pairs django-cms's editorial workflow with a decoupled frontend.

```python
# apps/cms_api/views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from cms.models import Page
from cms.models.placeholdermodel import Placeholder


@api_view(['GET'])
def page_content(request, page_id):
    """Return structured content for a CMS page, suitable for frontend rendering."""
    page = Page.objects.get(pk=page_id, publisher_is_draft=False)
    content = page.pagecontent_set.filter(language='en').first()

    placeholders = {}
    for ph in page.placeholders.all():
        plugins = []
        for plugin in ph.get_plugins('en').order_by('position'):
            instance = plugin.get_plugin_instance()[0]
            if instance:
                plugins.append({
                    'type': plugin.plugin_type,
                    'data': serialize_plugin(instance),
                })
        placeholders[ph.slot] = plugins

    return Response({
        'title': content.title if content else '',
        'slug': content.slug if content else '',
        'placeholders': placeholders,
    })


def serialize_plugin(instance):
    """Convert a plugin instance to a JSON-safe dict."""
    if hasattr(instance, 'essay'):
        return {
            'essay_title': instance.essay.title,
            'essay_slug': instance.essay.slug,
            'word_count': instance.essay.word_count,
            'stage': instance.essay.stage,
        }
    if hasattr(instance, 'body'):
        return {'body': instance.body}
    if hasattr(instance, 'image'):
        return {
            'image_url': instance.image.url if instance.image else None,
            'caption': getattr(instance, 'caption', ''),
        }
    return {}
```

This headless approach works well with HTMX partial loading (see htmx.md) or D3 chart data endpoints (see d3-django.md). The CMS handles editorial workflow and content structure; the API serves the data to whatever frontend consumes it.

### Frontend Integration

CMS plugin templates use the same Tailwind utility classes and Cotton components as the rest of the application. See tailwind.md for styling patterns and templates.md for Cotton component conventions.

```html
{# templates/plugins/essay_highlight.html #}
{% load static %}
<div class="bg-surface rounded-lg border border-outline p-6 shadow-sm">
    <h3 class="text-headline-md font-semibold text-on-surface mb-2">
        <a href="{% url 'content:essay-detail' essay.slug %}"
           class="hover:text-primary">
            {{ essay.title }}
        </a>
    </h3>
    {% if show_stage %}
    <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-label-md
        {% if essay.stage == 'published' %}bg-success-container text-success
        {% elif essay.stage == 'production' %}bg-info-container text-info
        {% elif essay.stage == 'research' %}bg-warning-container text-warning
        {% else %}bg-surface-dim text-on-surface-variant{% endif %}">
        {{ essay.get_stage_display }}
    </span>
    {% endif %}
    {% if show_word_count %}
    <p class="text-body-md text-on-surface-variant mt-2">
        {{ essay.word_count|intcomma }} words
    </p>
    {% endif %}
</div>
```

For interactive CMS plugins (charts, timelines, expandable sections), combine the plugin template with Alpine.js directives (see alpine.md) or D3 visualizations (see d3-django.md).

## Anti-Patterns

- **Single TextField as a CMS.** Works for blogs, becomes unmaintainable the moment you need structured content, reordering, or different content types on the same page.
- **Building a custom CMS from scratch** when django-cms or Wagtail covers your requirements. Custom CMS implementations accumulate edge cases for years.
- **Tight coupling between content and presentation.** Content models describe what the content is, not how it looks. Templates handle presentation. This allows redesigns without data migrations.
- **No versioning on editable content.** If non-developers edit content, they will delete something important. Version history is not optional.
- **Skipping content permissions.** Even in small teams, restrict who can publish vs draft. A workflow catches errors before they go live.
