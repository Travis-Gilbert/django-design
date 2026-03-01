# Django Templates and Components Reference

## Template Architecture

### Base Template Pattern

Every project needs a well-structured base template. Build it in layers.

```html
{# templates/base.html #}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}{% endblock %} | {{ site_name }}</title>

    {# Base styles that every page needs #}
    {% block base_css %}
        <link rel="stylesheet" href="{% static 'css/main.css' %}">
    {% endblock %}

    {# Page-specific styles #}
    {% block extra_css %}{% endblock %}

    {# Form media: widgets that declare CSS/JS dependencies #}
    {% block form_media %}{% endblock %}
</head>
<body class="{% block body_class %}{% endblock %}">

    {% block navigation %}
        {% include 'includes/nav.html' %}
    {% endblock %}

    {% block messages %}
        {% for message in messages %}
            <div class="alert alert-{{ message.tags }}">{{ message }}</div>
        {% endfor %}
    {% endblock %}

    <main>
        {% block content %}{% endblock %}
    </main>

    {% block footer %}
        {% include 'includes/footer.html' %}
    {% endblock %}

    {# Base scripts #}
    {% block base_js %}
        <script src="{% static 'js/main.js' %}"></script>
    {% endblock %}

    {# Page-specific scripts #}
    {% block extra_js %}{% endblock %}
</body>
</html>
```

### Template Inheritance Strategy

Think of template inheritance in three layers:

1. **`base.html`**: Site-wide structure (head, nav, footer, scripts).
2. **Section bases** (`base_studio.html`, `base_research.html`): Shared layout for a section of the site (sidebar, section nav, breadcrumbs).
3. **Page templates** (`content/essay_list.html`): The actual page content.

```html
{# templates/base_studio.html #}
{% extends 'base.html' %}

{% block body_class %}studio{% endblock %}

{% block content %}
<div class="studio-layout">
    <aside class="sidebar">
        {% block sidebar %}
            {% include 'studio/includes/sidebar.html' %}
        {% endblock %}
    </aside>
    <section class="main-content">
        {% block page_header %}{% endblock %}
        {% block page_content %}{% endblock %}
    </section>
</div>
{% endblock %}
```

### Custom Template Tags and Filters

Use template tags for reusable rendering logic. Use filters for value transformations.

```python
# apps/core/templatetags/core_tags.py
from django import template

register = template.Library()


@register.inclusion_tag('includes/pagination.html', takes_context=True)
def render_pagination(context, page_obj):
    """Reusable pagination component."""
    return {
        'page_obj': page_obj,
        'request': context['request'],
    }


@register.filter
def word_count(value):
    """Return the word count of a text string."""
    if not value:
        return 0
    return len(value.split())


@register.simple_tag(takes_context=True)
def active_nav(context, url_name, css_class='active'):
    """Return active class if current path matches the named URL."""
    from django.urls import reverse
    try:
        if context['request'].path == reverse(url_name):
            return css_class
    except Exception:
        pass
    return ''
```

### Template Organization

```
templates/
    base.html                    # site-wide base
    base_studio.html             # content studio section base
    base_research.html           # research section base (if separate)
    includes/
        nav.html                 # shared navigation
        footer.html              # shared footer
        pagination.html          # reusable pagination component
    studio/
        includes/
            sidebar.html         # studio-specific sidebar
    content/
        essay_list.html          # full page: extends base_studio
        _essay_list_partial.html # partial: just the table/cards (for HTMX)
        essay_detail.html
        _essay_sidebar.html      # partial used with {% include %}
        essay_edit.html
    cotton/                      # django-cotton components
        card.html
        button/
            filled.html
            outlined.html
        badge.html
    widgets/                     # custom form widget templates
        color_picker.html
        autocomplete.html
```

**Naming conventions:**
- Prefix partials with underscore: `_essay_list_partial.html`. This signals "not a full page."
- Cotton components go in `templates/cotton/` (django-cotton's default lookup).
- Group templates by app, not by type (not `templates/forms/`, but `templates/content/essay_edit.html`).

## Component Library: django-cotton

django-cotton provides a component system that uses HTML-like syntax. It fits naturally into Django templates without a build step.

### Component Definition

```html
{# templates/cotton/card.html #}
<c-vars
    class="rounded-lg shadow-md bg-surface p-4"
    elevated="false" />

<div class="{{ class }} {% if elevated %}shadow-lg{% endif %}" {{ attrs }}>
    {% if slot_header is defined %}
    <div class="card-header border-b pb-2 mb-3">
        {{ slot_header }}
    </div>
    {% endif %}

    <div class="card-body">
        {{ slot }}
    </div>

    {% if slot_actions is defined %}
    <div class="card-actions flex justify-end gap-2 pt-3 border-t mt-3">
        {{ slot_actions }}
    </div>
    {% endif %}
</div>
```

### Component Usage

```html
<c-card elevated>
    <c-slot name="header">
        <h3>{{ essay.title }}</h3>
    </c-slot>

    <p>Stage: {{ essay.get_stage_display }}</p>
    <p>Tags: {{ essay.tags|join:", " }}</p>

    <c-slot name="actions">
        <c-button.filled href="{% url 'content:essay-edit' essay.slug %}">
            Edit
        </c-button.filled>
    </c-slot>
</c-card>
```

### Component Naming Conventions

- Files use snake_case: `card_list.html`, `button.html`
- Templates reference them with kebab-case: `<c-card-list>`
- Variants use dot notation: `<c-button.filled>`, `<c-button.outlined>`
- Variant files live in subfolders: `cotton/button/filled.html`

### Component Design Principles

- Use `<c-vars>` to declare defaults. Every attribute should have a sensible default.
- Use `{{ slot }}` for the primary content, named slots for structured areas (header, actions, leading, trailing).
- Boolean attributes reduce boilerplate: `<c-button disabled>` rather than `<c-button disabled="true">`.
- Dynamic values use a colon prefix: `<c-component :disabled="is_readonly">`.
- Always pass `{{ attrs }}` to the root element so callers can add custom attributes.

### Data Table Component

A practical component for the content publishing domain:

```html
{# templates/cotton/data_table.html #}
<c-vars
    class=""
    striped="true"
    hoverable="true"
    empty_message="No results found." />

<div class="overflow-x-auto {{ class }}" {{ attrs }}>
    <table class="w-full {% if striped %}table-striped{% endif %} {% if hoverable %}table-hover{% endif %}">
        {% if slot_head is defined %}
        <thead>
            {{ slot_head }}
        </thead>
        {% endif %}

        <tbody>
            {{ slot }}
        </tbody>

        {% if slot_foot is defined %}
        <tfoot>
            {{ slot_foot }}
        </tfoot>
        {% endif %}
    </table>

    {% if slot_empty is defined %}
        {{ slot_empty }}
    {% else %}
        {# Shown when slot is empty via JS or server logic #}
    {% endif %}
</div>
```

### Form Field Component

Wraps Django form fields with consistent styling:

```html
{# templates/cotton/form_field.html #}
<c-vars
    class=""
    required="false"
    help="" />

<div class="form-field {{ class }} {% if field.errors %}has-error{% endif %}" {{ attrs }}>
    <label for="{{ field.id_for_label }}">
        {{ field.label }}
        {% if required %}<span class="text-error">*</span>{% endif %}
    </label>
    {{ field }}
    {% if help %}
        <span class="help-text">{{ help }}</span>
    {% elif field.help_text %}
        <span class="help-text">{{ field.help_text }}</span>
    {% endif %}
    {% for error in field.errors %}
        <span class="error-message">{{ error }}</span>
    {% endfor %}
</div>
```

Usage:

```html
<form method="post">
    {% csrf_token %}
    <c-form-field :field="form.title" required />
    <c-form-field :field="form.slug" help="URL-friendly identifier. Must be unique." />
    <c-form-field :field="form.summary" />
    <c-button.filled type="submit">Save Essay</c-button.filled>
</form>
```

## Advanced Cotton Patterns

### Dynamic Attributes

Cotton supports two syntaxes for passing non-string data to components.

**Quoteless syntax** for simple values (variables, booleans, integers):

```html
<c-badge active=True />
<c-counter start=42 />
<c-essay-card :essay="essay" />
```

**Colon prefix** for complex expressions (lists, dicts, quoted strings):

```html
<c-select :options="['published', 'drafting', 'research']" />
<c-chart :config="{'type': 'bar', 'stacked': True}" />
<c-form-field :errors="form.title.errors" />
```

The colon prefix evaluates Python expressions and preserves type information. Without it, values are always strings.

### Attribute Merging and Proxying

Pass a dictionary of attributes that merge into the component's `{{ attrs }}`. Build wrapper components that transparently pass attributes to inner components:

```html
{# templates/cotton/labeled_input.html #}
<c-vars label="" required="false" />

<div class="form-group">
    <label>{{ label }} {% if required %}<span class="text-error">*</span>{% endif %}</label>
    <c-input :attrs="attrs" />
</div>
```

Variables declared in `<c-vars />` are excluded from `{{ attrs }}`, so `label` and `required` configure the wrapper while all other attributes pass through to the inner `<c-input>`.

### Dynamic Component Selection

Use `<c-component>` with the `is` attribute to select components at runtime:

```html
{# Render different stage icons based on essay stage #}
<c-component is="icons.{{ essay.stage }}" />

{# From a variable #}
<c-component :is="card_type" />
```

This eliminates long `{% if %}` chains for component switching:

```html
{# Instead of: #}
{% if type == 'essay' %}<c-card.essay ... />{% elif type == 'source' %}<c-card.source ... />{% endif %}

{# Use: #}
<c-component is="card.{{ type }}" :data="item" />
```

### Cotton + Alpine.js Integration

Cotton converts kebab-case attributes to snake_case internally. Use `::` (double colon) to escape Cotton's colon prefix and output a literal `:` for Alpine's `x-bind`:

```html
{# templates/cotton/tabs.html #}
<c-vars />

<div x-data="{ currentTab: null, tabs: [] }" {{ attrs }}>
    <nav class="flex gap-2 border-b">
        <template x-for="tab in tabs">
            <button @click="currentTab = tab"
                    x-text="tab"
                    ::class="currentTab === tab ? 'border-b-2 border-primary font-semibold' : 'text-on-surface-variant'">
            </button>
        </template>
    </nav>
    <div class="py-4">
        {{ slot }}
    </div>
</div>
```

```html
{# templates/cotton/tab.html #}
<c-vars name="" />

<div x-data
     x-show="currentTab === '{{ name }}'"
     x-init="tabs.push('{{ name }}')">
    {{ slot }}
</div>
```

Usage:

```html
<c-tabs>
    <c-tab name="Details">
        {% include 'content/_tab_details.html' %}
    </c-tab>
    <c-tab name="Sources">
        {% include 'content/_tab_sources.html' %}
    </c-tab>
    <c-tab name="History">
        {% include 'content/_tab_history.html' %}
    </c-tab>
</c-tabs>
```

See alpine.md for more Alpine + Cotton pairing patterns.

### Context Isolation

By default, Cotton components inherit the parent template's context. Use `only` to prevent context leakage:

```html
<c-essay-card :essay="essay" only />
```

The `only` attribute ensures the component receives only its explicit attributes, not the full parent context. Use it for components that should be self-contained and reusable across different pages.

## django-material (Material Design 3)

For full Material Design 3 integration, django-material provides pre-built components with accessibility and responsive design built in.

```python
# settings/base.py
INSTALLED_APPS = [
    'material',
    # ...
]
```

```html
{% extends "material/base.html" %}
{% block content %}
    <c-button.filled>Save Draft</c-button.filled>
    <c-button.outlined>Cancel</c-button.outlined>

    <c-card>
        <c-slot name="headline">Essay Details</c-slot>
        {{ essay.title }}
    </c-card>
{% endblock %}
```

Key integration points: semantic color roles (primary, secondary, tertiary, surface), Unpoly.js for SPA-like navigation, peer selectors for form field states, and ARIA attributes built into every component. See design-system.md for color and typography patterns.

## Context Processors

Use context processors to make data available to every template without passing it through every view.

```python
# apps/core/context_processors.py
def site_settings(request):
    """Make site-wide settings available in all templates."""
    return {
        'site_name': 'Content Studio',
        'support_email': 'support@example.com',
    }


def user_permissions(request):
    """Pre-compute common permission checks for the navbar."""
    if not request.user.is_authenticated:
        return {'can_manage_content': False, 'can_view_reports': False}
    return {
        'can_manage_content': request.user.has_perm('content.change_essay'),
        'can_view_reports': request.user.has_perm('content.view_report'),
    }
```

```python
# settings/base.py
TEMPLATES = [{
    'OPTIONS': {
        'context_processors': [
            # Django defaults...
            'apps.core.context_processors.site_settings',
            'apps.core.context_processors.user_permissions',
        ],
    },
}]
```

## Anti-Patterns

- **Fat templates with business logic.** Templates should display data, not compute it. If you have `{% if essay.stage == 'drafting' and not essay.summary %}`, that logic belongs on the model as a property or method.
- **Hardcoding URLs.** Always use `{% url 'app:name' %}` in templates and `reverse()` in Python. Hardcoded paths break when URL patterns change.
- **Mixing component libraries.** Pick one component approach (cotton, django-material, plain templates) and use it consistently. Mixing creates maintenance nightmares.
- **Deep template inheritance.** Three layers (base, section, page) is the limit. Four or more layers make it nearly impossible to trace where a block is defined or overridden.
- **Logic in {% include %}.** If an included template needs its own queryset or complex context, it should be a view (possibly called via HTMX), not a template include with `{% with %}` gymnastics.
