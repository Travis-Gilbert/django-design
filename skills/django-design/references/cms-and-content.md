# Django CMS and Content Management Reference

## Content Architecture

Every application eventually needs some form of user-editable content. The question is how structured that content should be. On one end: a single `TextField` that holds raw HTML. On the other end: a full CMS with page trees, placeholders, versioned plugins, and editorial workflows. Most projects land somewhere in the middle.

This reference covers the spectrum, from simple flat content models through structured page hierarchies, drawing patterns from django-cms and real-world content systems.

## Flat Content Models

The simplest approach. A model with a title, body, and metadata. Good for blogs, news sections, FAQ entries, and any content type where the structure is uniform.

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

When content needs parent-child relationships (site navigation, documentation trees, nested pages), you need a tree structure. The two main approaches in Django are django-treebeard (used by django-cms) and django-mptt.

### Using django-treebeard

```python
# pip install django-treebeard

from treebeard.mp_tree import MP_Node


class Page(MP_Node):
    """Hierarchical page structure using materialized path trees."""

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
        indexes = [
            models.Index(fields=['slug', 'depth']),
        ]

    def get_absolute_url(self):
        """Build URL from ancestor slugs."""
        ancestors = self.get_ancestors()
        parts = [a.slug for a in ancestors] + [self.slug]
        return '/' + '/'.join(parts) + '/'

    @classmethod
    def get_published_tree(cls):
        """Return only published pages, maintaining tree structure."""
        return cls.objects.filter(is_published=True).order_by('path')
```

**Tree library comparison:**
- **django-treebeard** (MP_Node): Materialized path storage. Fast reads, consistent writes. Used by django-cms. Handles deep nesting well.
- **django-mptt**: Modified Preorder Tree Traversal. Fast reads, but tree corruption can happen on concurrent writes. Requires `mptt.register()` or inheriting from `MPTTModel`.
- **django-treebeard** (AL_Node): Adjacency list. Simple, but slow for deep tree queries. Fine for shallow trees (2-3 levels).

### URL Resolution for Page Trees

```python
# apps/pages/views.py
from django.http import Http404


def page_detail(request, path=''):
    """Resolve a URL path to a page in the tree."""
    slugs = [s for s in path.split('/') if s]

    if not slugs:
        # Root page
        try:
            page = Page.get_first_root_node()
        except Page.DoesNotExist:
            raise Http404
    else:
        # Walk the tree slug by slug
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

This is the pattern that makes django-cms powerful. Instead of a single body field, pages contain "placeholders" (named content regions), and each placeholder holds an ordered list of "plugins" (typed content blocks).

### Building Your Own Plugin System

You do not need django-cms to use this pattern. Here is a minimal implementation:

```python
class Placeholder(models.Model):
    """A named content region on a page."""
    slot = models.CharField(max_length=255, db_index=True)
    page = models.ForeignKey('Page', on_delete=models.CASCADE, related_name='placeholders')

    class Meta:
        unique_together = ['slot', 'page']

    def __str__(self):
        return f'{self.page.title} / {self.slot}'

    def get_plugins(self):
        return self.plugins.order_by('position')


class ContentPlugin(TimeStampedModel):
    """Base class for all content plugins in a placeholder."""
    placeholder = models.ForeignKey(
        Placeholder,
        on_delete=models.CASCADE,
        related_name='plugins',
    )
    position = models.PositiveIntegerField(default=0)
    plugin_type = models.CharField(max_length=100, db_index=True)

    class Meta:
        ordering = ['position']

    def get_plugin_instance(self):
        """Return the specific plugin subclass instance."""
        return getattr(self, self.plugin_type.lower(), self)


class TextPlugin(ContentPlugin):
    """Rich text content block."""
    body = models.TextField()

    def save(self, *args, **kwargs):
        self.plugin_type = 'textplugin'
        super().save(*args, **kwargs)


class ImagePlugin(ContentPlugin):
    """Image with optional caption."""
    image = models.ImageField(upload_to='plugins/images/%Y/%m/')
    caption = models.CharField(max_length=255, blank=True)
    alt_text = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        self.plugin_type = 'imageplugin'
        super().save(*args, **kwargs)


class CallToActionPlugin(ContentPlugin):
    """CTA block with heading, text, and button."""
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

    rendered_plugins = []
    for plugin in plugins:
        instance = plugin.get_plugin_instance()
        tmpl = PLUGIN_TEMPLATES.get(plugin.plugin_type, 'plugins/default.html')
        rendered_plugins.append({
            'instance': instance,
            'template': tmpl,
        })

    return {'plugins': rendered_plugins}
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
    <header>
        {% render_placeholder page "hero" %}
    </header>
    <main>
        {% render_placeholder page "content" %}
    </main>
    <aside>
        {% render_placeholder page "sidebar" %}
    </aside>
{% endblock %}
```

## Content Versioning

For applications that need editorial review, audit trails, or undo capability.

### Simple Version History

```python
class ArticleVersion(TimeStampedModel):
    """Immutable snapshot of an article at a point in time."""
    article = models.ForeignKey(
        Article,
        on_delete=models.CASCADE,
        related_name='versions',
    )
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
        last_version = article.versions.order_by('-version_number').first()
        next_number = (last_version.version_number + 1) if last_version else 1
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

The pattern django-cms uses: separate the "draft" content (what editors see) from the "live" content (what the public sees).

```python
class PageContent(TimeStampedModel):
    """Stores the actual content for a page, with draft/live separation."""
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
        """Copy draft content to the live version."""
        draft = cls.objects.get(page=page, language=language, is_draft=True)
        live, created = cls.objects.update_or_create(
            page=page,
            language=language,
            is_draft=False,
            defaults={
                'title': draft.title,
                'slug': draft.slug,
            },
        )
        return live
```

## django-cms Integration

When a project needs a full CMS, django-cms provides page trees, placeholders, plugins, permissions, multi-language support, and editorial workflows out of the box.

### Setup

```python
# pip install django-cms

# settings/base.py
INSTALLED_APPS = [
    'cms',
    'menus',
    'treebeard',
    'sekizai',
    # ...
]

CMS_TEMPLATES = [
    ('pages/default.html', 'Default'),
    ('pages/landing.html', 'Landing Page'),
    ('pages/sidebar.html', 'With Sidebar'),
]

CMS_PLACEHOLDER_CONF = {
    'content': {
        'plugins': ['TextPlugin', 'ImagePlugin', 'VideoPlugin'],
        'text_only_plugins': ['LinkPlugin'],
        'limits': {'TextPlugin': 10},
    },
    'sidebar': {
        'plugins': ['TextPlugin', 'CallToActionPlugin'],
    },
}
```

### Custom CMS Plugins

```python
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.models.pluginmodel import CMSPlugin


class PropertyHighlightModel(CMSPlugin):
    """Plugin that displays a featured property card."""
    property_ref = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
    )
    show_price = models.BooleanField(default=True)
    show_map = models.BooleanField(default=False)

    def __str__(self):
        return f'Property: {self.property_ref.address}'


@plugin_pool.register_plugin
class PropertyHighlightPlugin(CMSPluginBase):
    model = PropertyHighlightModel
    name = 'Property Highlight'
    render_template = 'plugins/property_highlight.html'
    cache = True

    def render(self, context, instance, placeholder):
        context.update({
            'property': instance.property_ref,
            'show_price': instance.show_price,
            'show_map': instance.show_map,
        })
        return context
```

### Key django-cms Concepts

**Pages** are tree nodes (using treebeard). They define structure and URL hierarchy but hold no content directly.

**PageContent** stores the translatable content (title, slug, meta description) for each page in each language.

**Placeholders** are named slots defined in templates using `{% placeholder "content" %}`. They are the content regions where plugins live.

**Plugins** are the actual content blocks. Each plugin is a model (storing data) paired with a plugin class (controlling rendering). The plugin model inherits from `CMSPlugin`, which provides tree structure (plugins can be nested), placeholder reference, and position ordering.

**Permissions** control who can edit which pages. django-cms provides page-level permissions, placeholder-level restrictions, and plugin type restrictions per placeholder.

## Anti-Patterns

- **Storing HTML in a single TextField and calling it a CMS.** This works for exactly one use case (a blog) and becomes unmaintainable the moment you need structured content, reordering, or different content types on the same page.
- **Building your own CMS from scratch** when django-cms or Wagtail covers your requirements. Custom CMS implementations accumulate edge cases for years. Use an existing solution and extend it.
- **Tight coupling between content structure and presentation.** Content models should describe what the content is, not how it looks. Templates handle presentation. This separation allows redesigns without data migrations.
- **No versioning on content that stakeholders edit.** If non-developers can edit content, they will eventually delete something important. Version history is not optional for content management.
- **Skipping permissions on content editing.** Even in small teams, restrict who can publish vs who can draft. A draft-to-publish workflow catches errors before they go live.
