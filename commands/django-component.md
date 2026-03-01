---
description: Scaffold a django-cotton component with props, slots, styling, and optional Alpine.js behavior
allowed-tools: Read, Write, Edit, Bash, Grep, Glob, AskUserQuestion
argument-hint: (interactive - no arguments needed)
---

# Django Cotton Component Scaffolding

Generate a reusable django-cotton component with proper props, slots, design token styling, and optional Alpine.js interactivity.

## Phase 1: Discover the Project

### Step 1: Check for Cotton setup

```bash
# Verify django-cotton is installed
grep -r "django_cotton\|cotton" */settings*.py settings/*.py 2>/dev/null
# Find existing components
find . -path "*/cotton/*.html" | head -30
# Find design tokens
find . -name "tokens.css" -o -name "tailwind.config*" | head -5
```

Read existing components to understand the project's component conventions (naming, styling approach, token usage).

### Step 2: Check for design system

Read `static/css/tokens.css` or `tailwind.config.js` if they exist. Note available semantic color tokens, typography scale, and spacing conventions.

### Step 3: Gather requirements

Ask the user three questions:

**Question 1: What type of component?**

Options:
- **Display** - Card, badge, stat, alert, avatar (shows data, no interaction)
- **Form** - Input wrapper, select, checkbox group, file upload (wraps form elements)
- **Navigation** - Tabs, breadcrumbs, sidebar item, pagination (navigation controls)
- **Interactive** - Dropdown, modal, accordion, tooltip (requires Alpine.js)
- **Data** - Table, list, chart wrapper (displays collections)
- **Custom** - Describe what you need

**Question 2: What should it be called?**

Free text. The name will be converted to the proper convention:
- File: `templates/cotton/{name}.html` (snake_case)
- Usage: `<c-{name}>` (kebab-case)
- Variants: `templates/cotton/{name}/{variant}.html` with `<c-{name}.{variant}>`

**Question 3: Does it need Alpine.js interactivity?**

Options:
- **No** - Static component, no client-side behavior
- **Toggle** - Show/hide content (accordion, expandable section)
- **Selection** - Track selected state (tabs, radio-like selection)
- **Full** - Custom Alpine.data() function (complex interactions)

## Phase 2: Design the Component

### Step 1: Define the API

Based on the component type and name, design:

**Props** (declared in `<c-vars />`):
- Each prop gets a sensible default
- Boolean props for visual variants (elevated, outlined, compact)
- String props for content variants (size, color, variant)

**Slots**:
- `{{ slot }}` for primary content
- Named slots for structured areas: `{{ slot_header }}`, `{{ slot_actions }}`, `{{ slot_leading }}`, `{{ slot_trailing }}`
- Conditional slot rendering with `{% if slot_header is defined %}`

**Styling**:
- Use semantic design tokens (bg-surface, text-primary, border-outline)
- Accept a `class` prop for caller customization
- Pass `{{ attrs }}` to root element for additional attributes

### Step 2: Confirm with user

Present the proposed component API:

```
Component: <c-{name}>
File: templates/cotton/{name}.html

Props:
  - class="" (additional CSS classes)
  - variant="default" (default | outlined | filled)
  - size="md" (sm | md | lg)

Slots:
  - {{ slot }} - main content
  - {{ slot_header }} - optional header area
  - {{ slot_actions }} - optional action buttons

Alpine: {none | toggle | selection | custom}

Usage example:
  <c-{name} variant="filled" size="lg">
    <c-slot name="header">Title</c-slot>
    Main content here
    <c-slot name="actions">
      <c-button.filled>Action</c-button.filled>
    </c-slot>
  </c-{name}>
```

Ask: "Does this component API look right? Any props or slots to add/remove?"

## Phase 3: Generate the Component

### Display Component Template

```html
{# templates/cotton/{name}.html #}
<c-vars
    class=""
    variant="default"
    size="md" />

{% with size_classes=size|yesno:"text-sm p-2,p-4,text-lg p-6" %}
<div class="rounded-lg border
            bg-surface border-outline
            {% if variant == 'filled' %}bg-primary text-on-primary border-0{% endif %}
            {% if variant == 'outlined' %}border-2{% endif %}
            {{ size_classes }}
            {{ class }}"
     {{ attrs }}>

    {% if slot_header is defined %}
    <div class="font-semibold mb-2 text-on-surface">
        {{ slot_header }}
    </div>
    {% endif %}

    <div class="text-on-surface-variant">
        {{ slot }}
    </div>

    {% if slot_actions is defined %}
    <div class="flex justify-end gap-2 mt-3 pt-3 border-t border-outline-variant">
        {{ slot_actions }}
    </div>
    {% endif %}
</div>
{% endwith %}
```

### Form Component Template

```html
{# templates/cotton/form_{name}.html #}
<c-vars
    class=""
    required="false"
    help=""
    error="" />

<div class="form-field {{ class }}
            {% if error %}has-error{% endif %}"
     {{ attrs }}>

    {% if slot_label is defined %}
    <label class="block text-label-lg text-on-surface mb-1">
        {{ slot_label }}
        {% if required %}<span class="text-error">*</span>{% endif %}
    </label>
    {% endif %}

    <div class="relative">
        {{ slot }}
    </div>

    {% if help %}
    <span class="text-body-md text-on-surface-variant mt-1 block">{{ help }}</span>
    {% endif %}

    {% if error %}
    <span class="text-body-md text-error mt-1 block">{{ error }}</span>
    {% endif %}
</div>
```

### Interactive Component Template (with Alpine)

```html
{# templates/cotton/{name}.html #}
<c-vars
    class=""
    open="false" />

<div x-data="{ open: {{ open }} }"
     class="{{ class }}"
     {{ attrs }}>

    <button @click="open = !open"
            class="flex items-center justify-between w-full
                   px-4 py-3 text-left
                   bg-surface hover:bg-surface-dim
                   border border-outline rounded-lg
                   transition-colors">
        <span class="font-medium text-on-surface">
            {% if slot_trigger is defined %}
                {{ slot_trigger }}
            {% else %}
                Toggle
            {% endif %}
        </span>
        <svg class="w-4 h-4 transition-transform text-on-surface-variant"
             ::class="open && 'rotate-180'">
            <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2"
                  fill="none" stroke-linecap="round"/>
        </svg>
    </button>

    <div x-show="open"
         x-transition:enter="transition ease-out duration-200"
         x-transition:enter-start="opacity-0 -translate-y-1"
         x-transition:enter-end="opacity-100 translate-y-0"
         x-transition:leave="transition ease-in duration-150"
         x-transition:leave-start="opacity-100 translate-y-0"
         x-transition:leave-end="opacity-0 -translate-y-1"
         class="mt-2 px-4 py-3 text-on-surface-variant">
        {{ slot }}
    </div>
</div>
```

### Data Component Template

```html
{# templates/cotton/{name}.html #}
<c-vars
    class=""
    striped="true"
    hoverable="true"
    empty_message="No results found." />

<div class="overflow-x-auto {{ class }}" {{ attrs }}>
    {% if slot_header is defined %}
    <div class="flex items-center justify-between px-4 py-3
                border-b border-outline-variant">
        {{ slot_header }}
    </div>
    {% endif %}

    <table class="w-full
                  {% if striped %}[&_tbody_tr:nth-child(even)]:bg-surface-dim{% endif %}
                  {% if hoverable %}[&_tbody_tr]:hover:bg-surface-dim{% endif %}">
        {% if slot_head is defined %}
        <thead class="bg-surface-dim text-left text-label-lg text-on-surface-variant">
            {{ slot_head }}
        </thead>
        {% endif %}

        <tbody class="divide-y divide-outline-variant">
            {{ slot }}
        </tbody>

        {% if slot_foot is defined %}
        <tfoot class="bg-surface-dim">
            {{ slot_foot }}
        </tfoot>
        {% endif %}
    </table>

    {% if slot_empty is defined %}
    <div class="py-8 text-center text-on-surface-variant">
        {{ slot_empty }}
    </div>
    {% endif %}
</div>
```

## Phase 4: Usage Examples and Summary

### Step 1: Generate usage example

Create a usage example that shows the component in context:

```html
{# Example usage in a page template #}
{% load cotton %}

<c-{name} variant="filled">
    <c-slot name="header">Essay Details</c-slot>

    <dl class="grid grid-cols-2 gap-4">
        <dt class="text-on-surface-variant">Title</dt>
        <dd>{{ essay.title }}</dd>
        <dt class="text-on-surface-variant">Stage</dt>
        <dd><c-badge color="{{ essay.stage }}">{{ essay.get_stage_display }}</c-badge></dd>
    </dl>

    <c-slot name="actions">
        <c-button.outlined href="{% url 'content:edit' essay.pk %}">
            Edit
        </c-button.outlined>
    </c-slot>
</c-{name}>
```

### Step 2: Summary

```
Generated component: <c-{name}>
  File: templates/cotton/{name}.html
  Props: {prop_count} ({prop_names})
  Slots: {slot_count} ({slot_names})
  Alpine: {yes/no}
  Tokens: {tokens_used}

Usage:
  <c-{name} {example_props}>
    Content here
  </c-{name}>

Related patterns:
  - See templates.md for Cotton component conventions
  - See design-system.md for semantic token usage
  - See alpine.md for Alpine + Cotton integration patterns
```
