# Django Forms, Templates, and Frontend Integration Reference

## Forms Architecture

Django forms are the bridge between user input and validated data. They handle rendering, validation, and cleaning in a single abstraction. The key is knowing when to use each form type and how to keep form logic from leaking into views.

### ModelForm Patterns

ModelForm is the default choice when a form maps directly to a model. Let the model do the heavy lifting.

```python
from django import forms
from apps.properties.models import Property


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'address', 'parcel_id', 'program',
            'purchase_date', 'purchase_price', 'buyer',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.TextInput(attrs={'placeholder': '123 Main St'}),
            'purchase_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
        help_texts = {
            'parcel_id': 'Format: XX-XX-XXX-XXX',
        }

    def clean_parcel_id(self):
        """Field-level validation. Runs after the field's built-in validation."""
        parcel_id = self.cleaned_data['parcel_id']
        if Property.objects.filter(parcel_id=parcel_id).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('A property with this parcel ID already exists.')
        return parcel_id

    def clean(self):
        """Cross-field validation. Runs after all field-level clean methods."""
        cleaned_data = super().clean()
        program = cleaned_data.get('program')
        price = cleaned_data.get('purchase_price')

        if program == 'featured_homes' and (not price or price < 1000):
            self.add_error(
                'purchase_price',
                'Featured Homes require a purchase price of at least $1,000.',
            )
        return cleaned_data
```

**When to use ModelForm vs plain Form:**
- `ModelForm`: When the form maps to a model and you want automatic field generation, validation, and `save()`.
- `Form`: When the form does not map to a single model (search forms, multi-model wizards, contact forms), or when you need full control over every field.

### Formsets

Formsets handle multiple instances of the same form on one page. Inline formsets tie child forms to a parent object.

```python
from django.forms import inlineformset_factory
from apps.properties.models import Property, ComplianceDocument

DocumentFormSet = inlineformset_factory(
    Property,
    ComplianceDocument,
    fields=['document_type', 'file', 'notes'],
    extra=1,          # one blank form for adding new documents
    can_delete=True,   # allow removing existing documents
    max_num=20,        # cap the total number
)


# In the view
def property_edit(request, pk):
    property_obj = get_object_or_404(Property, pk=pk)

    if request.method == 'POST':
        form = PropertyForm(request.POST, instance=property_obj)
        formset = DocumentFormSet(request.POST, request.FILES, instance=property_obj)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            return redirect('properties:detail', pk=property_obj.pk)
    else:
        form = PropertyForm(instance=property_obj)
        formset = DocumentFormSet(instance=property_obj)

    return render(request, 'properties/edit.html', {
        'form': form,
        'document_formset': formset,
    })
```

### Custom Widgets

Widgets control how a field renders. Override them for richer UI without changing validation.

```python
class ColorPickerWidget(forms.TextInput):
    template_name = 'widgets/color_picker.html'

    class Media:
        css = {'all': ('css/color-picker.css',)}
        js = ('js/color-picker.js',)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['swatches'] = ['#FF5733', '#33FF57', '#3357FF']
        return context


class AutocompleteWidget(forms.Select):
    """Select widget with server-side search. Works with HTMX or Unpoly."""
    template_name = 'widgets/autocomplete.html'

    def __init__(self, search_url, *args, **kwargs):
        self.search_url = search_url
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context['widget']['search_url'] = self.search_url
        return context
```

### Form Rendering Control

Django 5+ supports custom form renderers. Use them to globally control how forms render across the project.

```python
# settings/base.py
FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

# This tells Django to look in your templates/ directory for form templates.
# Override individual field templates:
# templates/django/forms/widgets/input.html
# templates/django/forms/widgets/select.html
```

For per-form rendering control:

```html
{# Render fields individually for maximum control #}
{% for field in form %}
<div class="form-field {% if field.errors %}has-error{% endif %}">
    <label for="{{ field.id_for_label }}">{{ field.label }}</label>
    {{ field }}
    {% if field.help_text %}
        <span class="help-text">{{ field.help_text }}</span>
    {% endif %}
    {% for error in field.errors %}
        <span class="error-message">{{ error }}</span>
    {% endfor %}
</div>
{% endfor %}
```

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
2. **Section bases** (`base_admin.html`, `base_portal.html`): Shared layout for a section of the site (sidebar, section nav, breadcrumbs).
3. **Page templates** (`properties/list.html`): The actual page content.

```html
{# templates/base_portal.html #}
{% extends 'base.html' %}

{% block body_class %}portal{% endblock %}

{% block content %}
<div class="portal-layout">
    <aside class="sidebar">
        {% block sidebar %}
            {% include 'portal/includes/sidebar.html' %}
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
def currency(value):
    """Format a decimal value as USD."""
    if value is None:
        return ''
    return f'${value:,.2f}'


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

## Component Library Integration

### django-cotton

django-cotton provides a component system that uses HTML-like syntax. It fits naturally into Django templates without a build step.

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

Usage in page templates:

```html
<c-card elevated>
    <c-slot name="header">
        <h3>{{ property.address }}</h3>
    </c-slot>

    <p>Status: {{ property.get_status_display }}</p>
    <p>Program: {{ property.program }}</p>

    <c-slot name="actions">
        <c-button.filled href="{% url 'properties:edit' property.pk %}">
            Edit
        </c-button.filled>
    </c-slot>
</c-card>
```

**Component naming conventions:**
- Files use snake_case: `card_list.html`, `button.html`
- Templates reference them with kebab-case: `<c-card-list>`
- Variants use dot notation: `<c-button.filled>`, `<c-button.outlined>`
- Variant files live in subfolders: `cotton/button/filled.html`

**Component design principles:**
- Use `<c-vars>` to declare defaults. Every attribute should have a sensible default.
- Use `{{ slot }}` for the primary content, named slots for structured areas (header, actions, leading, trailing).
- Boolean attributes reduce boilerplate: `<c-button disabled>` rather than `<c-button disabled="true">`.
- Dynamic values use a colon prefix: `<c-component :disabled="is_readonly">`.
- Always pass `{{ attrs }}` to the root element so callers can add custom attributes.

### django-material (Material Design 3)

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
    <c-button.filled>Submit Application</c-button.filled>
    <c-button.outlined>Cancel</c-button.outlined>

    <c-card>
        <c-slot name="headline">Property Details</c-slot>
        {{ property.address }}
    </c-card>
{% endblock %}
```

Key integration points: semantic color roles (primary, secondary, tertiary, surface), Unpoly.js for SPA-like navigation, peer selectors for form field states, and ARIA attributes built into every component.

## HTMX Integration

HTMX adds interactivity by issuing AJAX requests from HTML attributes. No JavaScript required for most patterns.

```python
# pip install django-htmx

# settings/base.py
INSTALLED_APPS = [
    'django_htmx',
    # ...
]
MIDDLEWARE = [
    # ...
    'django_htmx.middleware.HtmxMiddleware',
]
```

### Partial Template Pattern

The core HTMX pattern: views return full pages for normal requests, partial HTML for HTMX requests.

```python
def property_list(request):
    properties = Property.objects.active().select_related('buyer')

    program = request.GET.get('program')
    if program:
        properties = properties.filter(program=program)

    paginator = Paginator(properties, 25)
    page = paginator.get_page(request.GET.get('page'))

    template = 'properties/_list_partial.html' if request.htmx else 'properties/list.html'
    return render(request, template, {'page': page})
```

```html
{# templates/properties/list.html #}
{% extends 'base_portal.html' %}

{% block page_content %}
<div id="property-list">
    {% include 'properties/_list_partial.html' %}
</div>
{% endblock %}
```

### Common HTMX Patterns

```html
{# Inline editing #}
<span hx-get="{% url 'properties:edit-field' property.pk 'status' %}"
      hx-trigger="click"
      hx-swap="outerHTML"
      class="cursor-pointer hover:underline">
    {{ property.get_status_display }}
</span>

{# Search with debounce #}
<input type="search"
       name="q"
       hx-get="{% url 'properties:search' %}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#search-results"
       hx-indicator="#search-spinner"
       placeholder="Search properties...">

{# Infinite scroll #}
<div hx-get="{% url 'properties:list' %}?page={{ page.next_page_number }}"
     hx-trigger="intersect once"
     hx-swap="afterend"
     hx-select="#property-rows">
    Loading more...
</div>

{# Form submission with swap #}
<form hx-post="{% url 'properties:create' %}"
      hx-target="#property-list"
      hx-swap="afterbegin"
      hx-on::after-request="if(event.detail.successful) this.reset()">
    {% csrf_token %}
    {{ form.as_div }}
    <button type="submit">Add Property</button>
</form>
```

### HTMX + Django Messages

```python
import json
from django.http import HttpResponse


def htmx_message_response(request, message, level='success'):
    """For HTMX requests, return messages as an HX-Trigger header."""
    from django.contrib import messages
    messages.add_message(request, getattr(messages, level.upper()), message)

    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({
        'showMessage': {'message': message, 'level': level}
    })
    return response
```

## Unpoly Integration

Unpoly provides SPA-like navigation and modal/drawer patterns. It is the default in django-material.

```html
{# Navigation links become partial page updates #}
<a href="{% url 'properties:list' %}" up-target=".main-content">
    Properties
</a>

{# Open in a modal #}
<a href="{% url 'properties:create' %}" up-layer="new" up-size="large">
    New Property
</a>

{# Form submission in a drawer #}
<a href="{% url 'properties:edit' property.pk %}"
   up-layer="new drawer"
   up-on-accepted="up.reload('.property-detail')">
    Edit
</a>

{# Polling for live updates #}
<div up-poll up-interval="30000" up-source="{% url 'properties:status' property.pk %}">
    {{ property.get_status_display }}
</div>
```

**Unpoly vs HTMX decision:**
- HTMX: Minimal, attribute-driven, works well for adding interactivity to existing server-rendered apps. No opinions about navigation.
- Unpoly: More opinionated, handles navigation/history/modals/drawers out of the box. Better for building full SPA-like experiences without a JS framework.
- Both: Work with Django's CSRF, form validation, and template system. Neither requires a build step.

## Anti-Patterns

- **Duplicating validation in templates.** If the form validates `max_length=100`, do not also add a `maxlength="100"` attribute manually. Use `{{ form.field }}` and let Django handle it.
- **Fat templates with business logic.** Templates should display data, not compute it. If you have `{% if property.days_since_purchase > 180 and property.status == 'active' %}`, that logic belongs on the model as a property or method.
- **Hardcoding URLs.** Always use `{% url 'app:name' %}` in templates and `reverse()` in Python. Hardcoded paths break when URL patterns change.
- **Ignoring form media.** If a widget defines `class Media`, use `{{ form.media }}` in the template head. Forgetting this is why custom widgets "don't work."
- **Mixing component libraries.** Pick one component approach (cotton, django-material, plain templates) and use it consistently. Mixing creates maintenance nightmares.
