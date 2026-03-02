# HTMX + Django Reference

HTMX lets Django templates handle interactivity through HTML attributes instead of writing JavaScript. The server returns HTML fragments; HTMX swaps them into the page. This keeps business logic on the server and templates simple.

## Setup

```bash
pip install django-htmx
```

```python
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

Include HTMX in your base template:

```html
{# templates/base.html #}
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
```

Or serve it from static files for production (recommended).

## Core Attributes

Every HTMX interaction follows the same pattern: **trigger an event, make a request, swap the response.**

| Attribute | Purpose | Example |
|-----------|---------|---------|
| `hx-get` | GET request to URL | `hx-get="{% url 'content:essay-search' %}"` |
| `hx-post` | POST request to URL | `hx-post="{% url 'content:essay-create' %}"` |
| `hx-trigger` | Event that fires the request | `hx-trigger="click"`, `hx-trigger="keyup changed delay:300ms"` |
| `hx-target` | Where to put the response | `hx-target="#essay-list"` |
| `hx-swap` | How to insert the response | `hx-swap="innerHTML"`, `hx-swap="outerHTML"` |
| `hx-select` | CSS selector to extract from response | `hx-select="#results"` |
| `hx-include` | Additional elements to include in request | `hx-include="[name='csrf']"` |
| `hx-indicator` | Element to show during request | `hx-indicator="#spinner"` |
| `hx-boost` | Progressively enhance links/forms | `hx-boost="true"` |
| `hx-push-url` | Update browser URL bar | `hx-push-url="true"` |
| `hx-vals` | Additional values to submit | `hx-vals='{"page": "2"}'` |

### Swap strategies

| Strategy | Behavior |
|----------|----------|
| `innerHTML` | Replace children of target (default) |
| `outerHTML` | Replace the entire target element |
| `afterbegin` | Insert before first child |
| `beforeend` | Insert after last child |
| `afterend` | Insert after the target |
| `beforebegin` | Insert before the target |
| `delete` | Remove the target |
| `none` | No swap (fire-and-forget) |

Swap modifiers control timing: `hx-swap="innerHTML swap:200ms settle:100ms"`.

## CSRF Handling

Django requires CSRF tokens on POST requests. Configure HTMX to include them automatically:

```html
<body hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

This applies the CSRF token to every HTMX request within the body. No need to include `{% csrf_token %}` in HTMX-driven forms separately.

For forms that work both with and without HTMX (progressive enhancement):

```html
<form method="post" hx-post="{% url 'content:essay-create' %}">
    {% csrf_token %}
    {# form fields #}
    <button type="submit">Create Essay</button>
</form>
```

## Partial Template Pattern

The core Django + HTMX pattern: every interactive view has a full template and a partial template.

```python
# apps/content/views.py
from django.shortcuts import render

def essay_list(request):
    essays = Essay.objects.filter(draft=False).select_related('created_by')

    form = EssaySearchForm(request.GET)
    if form.is_valid():
        essays = form.filter_queryset(essays)

    paginator = Paginator(essays, 25)
    page = paginator.get_page(request.GET.get('page'))

    # Return partial for HTMX, full page for normal requests
    template = 'content/_list_partial.html' if request.htmx else 'content/essay_list.html'
    return render(request, template, {
        'page': page,
        'form': form,
    })
```

```html
{# templates/content/essay_list.html - full page #}
{% extends 'base_studio.html' %}

{% block page_content %}
<div id="essay-list-container">
    {% include 'content/_list_partial.html' %}
</div>
{% endblock %}
```

```html
{# templates/content/_list_partial.html - partial for HTMX swaps #}
<table class="w-full">
    <thead>
        <tr>
            <th>Title</th>
            <th>Stage</th>
            <th>Word Count</th>
            <th>Author</th>
        </tr>
    </thead>
    <tbody>
        {% for essay in page %}
        <tr>
            <td><a href="{% url 'content:essay-detail' essay.slug %}">{{ essay.title }}</a></td>
            <td>{{ essay.get_stage_display }}</td>
            <td>{{ essay.word_count|intcomma }}</td>
            <td>{{ essay.created_by.get_full_name }}</td>
        </tr>
        {% empty %}
        <tr><td colspan="4">No essays found.</td></tr>
        {% endfor %}
    </tbody>
</table>
{% include 'includes/pagination.html' with page_obj=page %}
```

**Naming convention:** Prefix partials with underscore: `_list_partial.html`. This signals "not a full page."

## Common Patterns

### Search with debounce

```html
<input type="search"
       name="q"
       placeholder="Search essays..."
       hx-get="{% url 'content:essay-list' %}"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#essay-list-container"
       hx-indicator="#search-spinner">
<span id="search-spinner" class="htmx-indicator">Searching...</span>
```

The `delay:300ms` prevents requests on every keystroke. The `changed` modifier only fires if the value actually changed.

### Inline editing

```html
{# Display mode #}
<div id="essay-{{ essay.pk }}-stage">
    <span>{{ essay.get_stage_display }}</span>
    <button hx-get="{% url 'content:edit-stage' essay.pk %}"
            hx-target="#essay-{{ essay.pk }}-stage"
            hx-swap="outerHTML">
        Edit
    </button>
</div>
```

```python
# View returns an edit form partial
def edit_essay_stage(request, pk):
    essay = get_object_or_404(Essay, pk=pk)

    if request.method == 'POST':
        form = EssayStageForm(request.POST, instance=essay)
        if form.is_valid():
            form.save()
            return render(request, 'content/_stage_display.html', {
                'essay': essay,
            })
    else:
        form = EssayStageForm(instance=essay)

    return render(request, 'content/_stage_edit.html', {
        'essay': essay,
        'form': form,
    })
```

### Infinite scroll

```html
{# templates/content/_list_partial.html #}
{% for essay in page %}
<div class="essay-card">
    {{ essay.title }} - {{ essay.get_stage_display }}
</div>
{% endfor %}

{% if page.has_next %}
<div hx-get="{% url 'content:essay-list' %}?page={{ page.next_page_number }}"
     hx-trigger="revealed"
     hx-swap="afterend"
     hx-select=".essay-card, [hx-trigger='revealed']">
    Loading more...
</div>
{% endif %}
```

The `revealed` trigger fires when the element scrolls into view. The `hx-select` extracts only the cards and the next trigger element from the response.

### Form submission with validation feedback

```html
<form hx-post="{% url 'content:essay-create' %}"
      hx-target="#form-container"
      hx-swap="outerHTML">
    {% csrf_token %}
    {% for field in form %}
    <div class="form-field {% if field.errors %}has-error{% endif %}">
        <label for="{{ field.id_for_label }}">{{ field.label }}</label>
        {{ field }}
        {% for error in field.errors %}
            <span class="error-message">{{ error }}</span>
        {% endfor %}
    </div>
    {% endfor %}
    <button type="submit">Create Essay</button>
</form>
```

```python
def essay_create(request):
    if request.method == 'POST':
        form = EssayForm(request.POST)
        if form.is_valid():
            essay = form.save()
            # Redirect for normal requests, HX-Redirect for HTMX
            if request.htmx:
                response = HttpResponse()
                response['HX-Redirect'] = reverse('content:essay-detail', kwargs={'slug': essay.slug})
                return response
            return redirect('content:essay-detail', slug=essay.slug)
    else:
        form = EssayForm()

    return render(request, 'content/_form.html', {'form': form})
```

### Django messages with HX-Trigger

Push Django messages to the frontend after HTMX actions:

```python
from django.contrib import messages

def publish_essay(request, pk):
    essay = get_object_or_404(Essay, pk=pk)
    essay.publish(reviewer=request.user)
    messages.success(request, f'Essay "{essay.title}" published.')

    response = render(request, 'content/_stage_display.html', {
        'essay': essay,
    })
    response['HX-Trigger'] = 'showMessages'
    return response
```

```html
{# In base.html, listen for the trigger and refresh the messages area #}
<div id="messages"
     hx-get="{% url 'core:messages' %}"
     hx-trigger="showMessages from:body"
     hx-swap="innerHTML">
    {% for message in messages %}
        <div class="alert alert-{{ message.tags }}">{{ message }}</div>
    {% endfor %}
</div>
```

## Out-of-Band (OOB) Swaps

Update multiple page sections from a single response:

```html
{# Main response content (swapped into hx-target) #}
<div id="essay-detail">
    {{ essay.title }} - {{ essay.get_stage_display }}
</div>

{# OOB content (swapped into its own target automatically) #}
<div id="sidebar-stats" hx-swap-oob="innerHTML">
    <p>Published: {{ stats.published_count }}</p>
    <p>In Production: {{ stats.production_count }}</p>
</div>
```

OOB swaps are useful when one action affects multiple page sections (e.g., publishing an essay updates the detail card and the sidebar stats).

## Response Headers

HTMX reads special response headers from the server:

| Header | Purpose |
|--------|---------|
| `HX-Redirect` | Client-side redirect |
| `HX-Refresh` | Full page refresh |
| `HX-Trigger` | Trigger client-side events |
| `HX-Retarget` | Change the swap target |
| `HX-Reswap` | Change the swap strategy |
| `HX-Push-Url` | Update browser URL |

```python
# Utility for setting HTMX response headers
from django.http import HttpResponse


def htmx_redirect(url):
    """Return an empty response that tells HTMX to redirect."""
    response = HttpResponse()
    response['HX-Redirect'] = url
    return response
```

## Boosted Navigation

`hx-boost="true"` progressively enhances regular links and forms. Clicks fetch the page via AJAX and swap the body, providing SPA-like navigation without changing templates:

```html
<nav hx-boost="true">
    <a href="{% url 'content:dashboard' %}">Dashboard</a>
    <a href="{% url 'content:essay-list' %}">Essays</a>
    <a href="{% url 'content:pipeline' %}">Pipeline</a>
</nav>
```

Boosted links automatically push URLs to the browser history. The server returns the full page; HTMX extracts and swaps the `<body>`.

## Loading Indicators

```html
<button hx-post="{% url 'content:publish-essay' essay.pk %}"
        hx-target="#essay-{{ essay.pk }}"
        hx-indicator="#publish-spinner-{{ essay.pk }}">
    Publish
</button>
<span id="publish-spinner-{{ essay.pk }}"
      class="htmx-indicator">
    Publishing...
</span>
```

HTMX automatically adds the `htmx-request` class to the triggering element during requests. Use CSS to show/hide indicators:

```css
.htmx-indicator { display: none; }
.htmx-request .htmx-indicator { display: inline; }
.htmx-request.htmx-indicator { display: inline; }
```

## Alternative: django-unicorn

django-unicorn provides a reactive component framework as an alternative to HTMX. It uses Python classes for component state and template directives for binding.

```python
# apps/content/components/essay_search.py
from django_unicorn.components import UnicornView

class EssaySearchView(UnicornView):
    search_query = ''
    stage_filter = ''
    essays = []

    def search(self):
        qs = Essay.objects.filter(draft=False)
        if self.search_query:
            qs = qs.filter(title__icontains=self.search_query)
        if self.stage_filter:
            qs = qs.filter(stage=self.stage_filter)
        self.essays = list(qs[:25])
```

```html
{# templates/unicorn/essay-search.html #}
<div>
    <input type="text"
           unicorn:model.defer="search_query"
           placeholder="Search essays...">
    <select unicorn:model="stage_filter">
        <option value="">All</option>
        <option value="published">Published</option>
        <option value="production">In Production</option>
    </select>
    <button unicorn:click="search">Search</button>

    {% for essay in essays %}
        <div>{{ essay.title }} - {{ essay.get_stage_display }}</div>
    {% endfor %}
</div>
```

**When to choose django-unicorn over HTMX:**
- You want two-way data binding without writing JavaScript
- The component has complex client-side state that would be awkward with pure HTMX
- Your team prefers Python-centric development over HTML attribute patterns

**When to choose HTMX:**
- You want minimal abstraction over HTTP
- The interaction pattern is request-response (fetch HTML, swap it in)
- You need to integrate with other JavaScript libraries (Alpine, D3)
- You want progressive enhancement that works without JavaScript

Do not mix both in the same project. Pick one approach for interactive server-rendered UI.

## Anti-Patterns

- **Returning JSON from HTMX endpoints.** HTMX expects HTML. If you need JSON, that is an API endpoint (see api.md), not an HTMX endpoint.
- **Fat partials that re-render the entire page.** Return only the HTML that changed. If your partial is 500 lines, it is not a partial.
- **Missing CSRF configuration.** Set `hx-headers` on `<body>` once instead of adding `{% csrf_token %}` to every HTMX form. Both approaches work, but the header approach is less error-prone.
- **No fallback for non-JS users.** Use `hx-boost` on navigation links and standard form submissions as the base. HTMX should enhance, not replace.
- **Forgetting `request.htmx` checks.** Always return the full page for non-HTMX requests. Users who open a link in a new tab should get a complete page, not a partial fragment.
- **Using hx-get for state-changing operations.** GET requests should be idempotent. Use `hx-post` (or `hx-put`, `hx-delete`) for operations that modify data.
