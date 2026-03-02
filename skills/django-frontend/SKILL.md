---
name: django-frontend
description: Use when the user asks about Django templates, template inheritance, django-cotton components, HTMX interactions, Alpine.js reactivity, Tailwind CSS styling, forms and form rendering, design systems, design tokens, responsive layouts, or any frontend work in a Django project.
version: 4.0.0
---

# Django Frontend: Templates, Components, Interactivity, and Design

This skill covers everything on the Django frontend stack: template architecture, django-cotton components, HTMX server-driven interactivity, Alpine.js client-side state, Tailwind CSS styling, Django forms, and design system conventions.

## The Django Frontend Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Page structure | Django templates | Base templates, inheritance, blocks |
| Components | django-cotton | Reusable UI components with props, slots, attributes |
| Server communication | HTMX | HTML-over-the-wire interactions without JavaScript |
| Client state | Alpine.js | Dropdowns, modals, tabs, toggles -- UI state only |
| Styling | Tailwind CSS | Utility-first CSS with design tokens |
| Forms | Django forms | Validation, rendering, formsets |
| Design system | CSS tokens | Semantic colors, typography, spacing |

## Reference Library

- **`references/templates.md`** -- Base template pattern, template inheritance, custom tags/filters, django-cotton components (definition, slots, props, dynamic attributes, Alpine integration), context processors
- **`references/views.md`** -- FBV vs CBV guidance, template-based views, URL patterns, middleware, pagination, file uploads, error handling
- **`references/htmx.md`** -- Core HTMX attributes with Django examples, partial template pattern, CSRF handling, search with debounce, inline editing, infinite scroll, OOB swaps, boosted navigation
- **`references/alpine.md`** -- Core directives (x-data, x-show, x-bind, x-model, x-for), Alpine + HTMX pairing patterns, Alpine + Cotton components, reusable data functions, transitions, passing Django data safely
- **`references/tailwind.md`** -- Django integration (django-tailwind and django-tailwind-cli), template usage, JIT and content scanning, responsive patterns, dark mode, component styling, production optimization
- **`references/forms.md`** -- ModelForm patterns, plain forms, formsets, custom widgets, form rendering control, validation order
- **`references/design-system.md`** -- Semantic color tokens, typography scale, spacing system, component-level tokens, Tailwind config mapping, Material Design 3 integration, light/dark theme switching

## Quick Guidance

### Templates

- Three layers max: base, section, page. Four or more layers make it impossible to trace where a block is defined.
- HTMX partials use underscore prefix: `_list_partial.html`. Full pages use plain names: `list.html`.
- Use `{% url %}` tags and `reverse()`. Hardcoded URLs in templates are always wrong.

### Cotton Components

- Define components in `templates/cotton/`. Props use `c-vars` for defaults.
- Use `{{ slot }}` for default content, named slots with `<c-slot name="actions">`.
- Pass Django data safely with `{{ attrs }}` for HTML attribute proxying.
- Integrate Alpine with double-colon syntax: `::x-data` in Cotton tags.

### HTMX

- Use `hx-get`/`hx-post` with `hx-target` and `hx-swap`. Return HTML partials, not JSON.
- Include CSRF token via `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` or meta tag middleware.
- Add `hx-indicator` for loading states. Add `hx-trigger="keyup changed delay:300ms"` for search debounce.
- Use `HtmxMiddleware` from django-htmx to detect `request.htmx` in views.

### Alpine.js

- Alpine handles UI state only. If you need server data, use HTMX.
- Pass Django data through `json_script` filter, never `{{ data|safe }}` in script tags.
- Use `Alpine.data()` for reusable component logic. Keep `x-data` inline for one-off toggles.

### Design System

- Use semantic tokens (`bg-primary`, `text-error`) instead of raw values (`bg-[#1e40af]`).
- Define tokens in `tokens.css` and map them through Tailwind config.
- Establish typography scale and spacing system before building templates.

## Anti-Patterns

- **`{{ data|safe }}` in JavaScript.** Use Django's `json_script` filter for XSS-safe data transfer to Alpine or D3.
- **Fat templates with business logic.** If you have complex conditionals, that logic belongs on the model as a property or method.
- **Hardcoded hex colors.** Use semantic tokens. Hardcoded colors break theme switching.
- **Mixing component systems.** Pick one (Cotton, plain templates) and use it consistently.
- **Alpine for server communication.** Use HTMX for server interactions. Alpine handles client-side state only.
- **Deep template inheritance.** Three layers is the limit.
- **Fixed-size SVG charts.** Always use `viewBox` for responsive D3 charts. See the django-d3 skill for visualization.

## Agents

| Agent | Focus |
|-------|-------|
| `template-specialist` | Templates, HTMX, Cotton, Alpine.js, template partials |
| `django-frontend` | Frontend integration review, accessibility, component conventions |
| `ui-designer` | Visual design, design systems, component libraries |
