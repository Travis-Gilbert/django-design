# Alpine.js + Django Reference

Alpine.js adds client-side interactivity to Django templates without a build step. It handles UI state (dropdowns, tabs, modals, toggles) that does not need a server round-trip. Pair it with HTMX for server-driven interactions (see htmx.md).

## Setup

Include Alpine in your base template:

```html
{# templates/base.html #}
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

Or install via npm and bundle it (if using a build step):

```bash
npm install alpinejs
```

```javascript
// static/js/main.js
import Alpine from 'alpinejs'
window.Alpine = Alpine
Alpine.start()
```

Place the script tag **before** the closing `</head>` with `defer`, or at the end of `<body>`. Alpine auto-initializes on `DOMContentLoaded`.

## Core Directives

### x-data: Declare reactive state

Every Alpine component starts with `x-data`. It defines the reactive data scope.

```html
{# Essay card with expandable details #}
<div x-data="{ expanded: false }">
    <div class="flex justify-between items-center">
        <h3>{{ essay.title }}</h3>
        <button @click="expanded = !expanded"
                x-text="expanded ? 'Hide Details' : 'Show Details'">
        </button>
    </div>
    <div x-show="expanded" x-transition>
        <dl>
            <dt>Slug</dt>
            <dd>{{ essay.slug }}</dd>
            <dt>Word Count</dt>
            <dd>{{ essay.word_count|intcomma }}</dd>
            <dt>Stage</dt>
            <dd>{{ essay.get_stage_display }}</dd>
        </dl>
    </div>
</div>
```

### x-show and x-if: Conditional rendering

`x-show` toggles CSS `display` (element stays in DOM). Use it for frequently toggled elements.

```html
<div x-data="{ showFilters: false }">
    <button @click="showFilters = !showFilters">
        Toggle Filters
    </button>
    <div x-show="showFilters" x-transition.duration.200ms>
        {% include 'content/_filter_form.html' %}
    </div>
</div>
```

`x-if` adds/removes the element from the DOM. Use it for content that is expensive to keep around or rarely shown:

```html
<template x-if="showConfirmDialog">
    <div class="modal-overlay">
        <div class="modal-content">
            <p>Are you sure you want to unpublish this essay?</p>
            <button @click="confirmUnpublish()">Confirm</button>
            <button @click="showConfirmDialog = false">Cancel</button>
        </div>
    </div>
</template>
```

### x-bind and x-on: Dynamic attributes and events

`x-bind` (shorthand `:`) binds attribute values. `x-on` (shorthand `@`) listens for events.

```html
<div x-data="{ selectedStage: '' }">
    <select x-model="selectedStage">
        <option value="">All Stages</option>
        <option value="published">Published</option>
        <option value="production">In Production</option>
        <option value="drafting">Drafting</option>
    </select>

    {# Dynamic class binding #}
    <span :class="{
        'bg-green-100 text-green-800': selectedStage === 'published',
        'bg-purple-100 text-purple-800': selectedStage === 'production',
        'bg-gray-100 text-gray-800': selectedStage === 'drafting',
    }">
        Stage indicator
    </span>
</div>
```

### x-model: Two-way binding on form inputs

```html
<div x-data="{ wordCount: {{ essay.word_count|default:'0' }} }">
    <label>Target Word Count</label>
    <input type="number" x-model="wordCount" step="100">
    <p x-show="wordCount > 5000" class="text-yellow-600">
        Long-form essay. Consider breaking into a series.
    </p>
</div>
```

### x-for: Loop rendering

```html
<div x-data="{ sources: {{ essay_sources_json }} }">
    <ul>
        <template x-for="source in sources" :key="source.id">
            <li>
                <span x-text="source.title"></span>
                <span x-text="source.source_type"></span>
                <button @click="sources = sources.filter(s => s.id !== source.id)">
                    Remove
                </button>
            </li>
        </template>
    </ul>
</div>
```

Use Django's `json_script` filter to pass data safely:

```html
{{ essay_sources|json_script:"sources-data" }}
<div x-data="{ sources: JSON.parse(document.getElementById('sources-data').textContent) }">
    {# ... #}
</div>
```

### x-effect: Reactive side effects

```html
<div x-data="{ search: '', results: [] }"
     x-effect="if (search.length > 2) { fetchResults(search) }">
    <input type="text" x-model="search" placeholder="Search...">
</div>
```

## Alpine + HTMX Pairing

Alpine handles client-side state (UI toggles, local validation, animations). HTMX handles server communication (fetching HTML, submitting forms). They complement each other without overlap.

### Pattern: Client-side validation before server submission

```html
<form hx-post="{% url 'content:essay-create' %}"
      hx-target="#form-container"
      x-data="{ valid: false, wordCount: 0, stage: '' }"
      x-effect="valid = (wordCount > 0 && stage !== '')"
      @htmx:before-request="if (!valid) { $event.preventDefault() }">

    <select x-model="stage" name="stage">
        <option value="">Select Stage</option>
        <option value="drafting">Drafting</option>
        <option value="research">Research</option>
    </select>

    <input type="number" x-model="wordCount" name="target_word_count" step="100">
    <p x-show="wordCount > 0 && wordCount < 500 && stage === 'research'"
       class="text-red-600">
        Research essays should target at least 500 words.
    </p>

    <button type="submit" :disabled="!valid"
            :class="valid ? 'bg-primary-600' : 'bg-gray-400 cursor-not-allowed'">
        Create Essay
    </button>
</form>
```

### Pattern: Tab navigation with HTMX content loading

```html
<div x-data="{ activeTab: 'details' }">
    <nav class="flex gap-4 border-b">
        <button @click="activeTab = 'details'"
                :class="activeTab === 'details' ? 'border-b-2 border-primary-600 font-semibold' : ''"
                hx-get="{% url 'content:essay-details' essay.pk %}"
                hx-target="#tab-content"
                hx-trigger="click"
                hx-swap="innerHTML">
            Details
        </button>
        <button @click="activeTab = 'sources'"
                :class="activeTab === 'sources' ? 'border-b-2 border-primary-600 font-semibold' : ''"
                hx-get="{% url 'content:essay-sources' essay.pk %}"
                hx-target="#tab-content"
                hx-trigger="click"
                hx-swap="innerHTML">
            Sources
        </button>
        <button @click="activeTab = 'revisions'"
                :class="activeTab === 'revisions' ? 'border-b-2 border-primary-600 font-semibold' : ''"
                hx-get="{% url 'content:essay-revisions' essay.pk %}"
                hx-target="#tab-content"
                hx-trigger="click"
                hx-swap="innerHTML">
            Revisions
        </button>
    </nav>
    <div id="tab-content" class="py-4">
        {% include 'content/_tab_details.html' %}
    </div>
</div>
```

Alpine manages the active tab styling; HTMX fetches the tab content from the server.

## Alpine + Cotton Components

Cotton components can accept Alpine directives. Use the double-colon (`::`) prefix to pass Alpine bindings through Cotton's attribute system:

```html
{# templates/cotton/dropdown.html #}
<c-vars label="Select" />

<div x-data="{ open: false }" class="relative" {{ attrs }}>
    <button @click="open = !open"
            @click.outside="open = false"
            class="flex items-center gap-2 px-3 py-2 border rounded">
        <span>{{ label }}</span>
        <svg :class="open && 'rotate-180'" class="w-4 h-4 transition-transform">
            {# chevron icon #}
        </svg>
    </button>
    <div x-show="open"
         x-transition:enter="transition ease-out duration-100"
         x-transition:enter-start="opacity-0 scale-95"
         x-transition:enter-end="opacity-100 scale-100"
         x-transition:leave="transition ease-in duration-75"
         x-transition:leave-start="opacity-100 scale-100"
         x-transition:leave-end="opacity-0 scale-95"
         class="absolute mt-1 w-full bg-white border rounded shadow-lg z-10">
        {{ slot }}
    </div>
</div>
```

Usage:

```html
<c-dropdown label="Stage">
    <a href="?stage=published" class="block px-4 py-2 hover:bg-gray-100">Published</a>
    <a href="?stage=production" class="block px-4 py-2 hover:bg-gray-100">In Production</a>
    <a href="?stage=drafting" class="block px-4 py-2 hover:bg-gray-100">Drafting</a>
</c-dropdown>
```

## Reusable Data Functions

For complex components used in multiple places, register Alpine data functions globally:

```javascript
// static/js/alpine-components.js
document.addEventListener('alpine:init', () => {
    Alpine.data('essayFilter', () => ({
        filters: {
            stage: '',
            contentType: '',
            dateFrom: '',
            dateTo: '',
        },
        activeFilterCount: 0,

        init() {
            this.$watch('filters', () => {
                this.activeFilterCount = Object.values(this.filters)
                    .filter(v => v !== '').length
            })
        },

        reset() {
            this.filters = { stage: '', contentType: '', dateFrom: '', dateTo: '' }
        },

        toQueryString() {
            return new URLSearchParams(
                Object.fromEntries(
                    Object.entries(this.filters).filter(([_, v]) => v !== '')
                )
            ).toString()
        },
    }))
})
```

```html
<div x-data="essayFilter">
    <div class="flex items-center gap-4">
        <select x-model="filters.stage" name="stage">
            <option value="">All Stages</option>
            <option value="published">Published</option>
            <option value="production">In Production</option>
        </select>
        <button @click="reset()" x-show="activeFilterCount > 0">
            Clear (<span x-text="activeFilterCount"></span>)
        </button>
    </div>
</div>
```

## Transitions and Animations

Alpine provides built-in transition directives for show/hide animations:

```html
{# Fade transition #}
<div x-show="visible" x-transition>
    Content fades in/out
</div>

{# Custom transition #}
<div x-show="open"
     x-transition:enter="transition ease-out duration-200"
     x-transition:enter-start="opacity-0 -translate-y-2"
     x-transition:enter-end="opacity-100 translate-y-0"
     x-transition:leave="transition ease-in duration-150"
     x-transition:leave-start="opacity-100 translate-y-0"
     x-transition:leave-end="opacity-0 -translate-y-2">
    Slide-fade content
</div>
```

For Tailwind CSS integration, use transition classes directly:

```html
<div x-show="expanded"
     x-transition:enter="transition-all duration-300 ease-out"
     x-transition:enter-start="max-h-0 opacity-0"
     x-transition:enter-end="max-h-96 opacity-100"
     x-transition:leave="transition-all duration-200 ease-in"
     x-transition:leave-start="max-h-96 opacity-100"
     x-transition:leave-end="max-h-0 opacity-0"
     class="overflow-hidden">
    {{ slot }}
</div>
```

## Passing Django Data to Alpine

Use Django's `json_script` filter for safe data transfer:

```python
# views.py
def essay_detail(request, slug):
    essay = get_object_or_404(Essay, slug=slug)
    pipeline_data = {
        'target': essay.target_word_count or 3000,
        'current': essay.word_count,
        'sources': list(essay.source_links.values_list('source_type', flat=True)),
    }
    return render(request, 'content/essay_detail.html', {
        'essay': essay,
        'pipeline_json': pipeline_data,
    })
```

```html
{{ pipeline_json|json_script:"pipeline-data" }}
<div x-data="{ pipeline: JSON.parse(document.getElementById('pipeline-data').textContent) }">
    <p>Progress: <span x-text="pipeline.current"></span> / <span x-text="pipeline.target"></span> words</p>
    <div class="w-full bg-gray-200 rounded-full h-2">
        <div class="bg-green-600 h-2 rounded-full"
             :style="`width: ${Math.min(pipeline.current / pipeline.target * 100, 100)}%`">
        </div>
    </div>
</div>
```

The `json_script` filter escapes the data for safe embedding in HTML. Never use `{{ data|safe }}` inside JavaScript - it is vulnerable to XSS.

## Anti-Patterns

- **Fetching data with Alpine instead of HTMX.** Alpine's `$fetch` exists but returns JSON. Use HTMX for server interactions that return HTML. Use Alpine only for client-side state.
- **Complex state management in Alpine.** If a component has more than 5-6 reactive properties or needs to share state across distant parts of the page, consider whether the logic belongs on the server instead.
- **Inline JavaScript in x-data.** Keep `x-data` expressions short. For anything beyond 3-4 lines, extract it to an `Alpine.data()` function in a JS file.
- **Using Alpine for form submission.** Let HTMX or standard form submission handle POST requests. Alpine should manage UI state (showing/hiding, validation feedback, animations), not HTTP communication.
- **Mixing Alpine and jQuery.** Alpine replaces jQuery for reactive UI patterns. Do not use both. Alpine's `$refs`, `$dispatch`, and `$watch` cover the common jQuery use cases.
