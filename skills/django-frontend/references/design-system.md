# Design System Reference

This reference covers the design tokens, color system, typography scale, and component conventions that keep a Django project's frontend consistent. It bridges the gap between Tailwind utility classes (see tailwind.md), Cotton components (see templates.md), and Material Design 3 integration.

## Semantic Color Roles

Define colors by purpose, not by hue. This enables theme switching (light/dark, brand variations) without changing templates.

### Color Token Architecture

```css
/* static/css/tokens.css */
:root {
    /* Brand colors */
    --color-primary: #1e40af;
    --color-primary-light: #3b82f6;
    --color-primary-dark: #1e3a8a;
    --color-secondary: #7c3aed;
    --color-secondary-light: #a78bfa;

    /* Semantic surface colors */
    --color-surface: #ffffff;
    --color-surface-dim: #f9fafb;
    --color-surface-bright: #ffffff;
    --color-on-surface: #111827;
    --color-on-surface-variant: #6b7280;

    /* Status colors */
    --color-success: #16a34a;
    --color-success-container: #dcfce7;
    --color-warning: #eab308;
    --color-warning-container: #fef9c3;
    --color-error: #dc2626;
    --color-error-container: #fee2e2;
    --color-info: #2563eb;
    --color-info-container: #dbeafe;

    /* Border and outline */
    --color-outline: #d1d5db;
    --color-outline-variant: #e5e7eb;
}

/* Dark theme override */
.dark {
    --color-primary: #60a5fa;
    --color-primary-light: #93c5fd;
    --color-primary-dark: #3b82f6;
    --color-surface: #1f2937;
    --color-surface-dim: #111827;
    --color-surface-bright: #374151;
    --color-on-surface: #f9fafb;
    --color-on-surface-variant: #9ca3af;
    --color-outline: #4b5563;
    --color-outline-variant: #374151;
    --color-success-container: #14532d;
    --color-warning-container: #713f12;
    --color-error-container: #7f1d1d;
    --color-info-container: #1e3a5f;
}
```

### Tailwind Configuration

Map semantic tokens to Tailwind utility classes:

```javascript
// tailwind.config.js (v3) or via @theme in v4 CSS
module.exports = {
    theme: {
        extend: {
            colors: {
                primary: {
                    DEFAULT: 'var(--color-primary)',
                    light: 'var(--color-primary-light)',
                    dark: 'var(--color-primary-dark)',
                },
                secondary: {
                    DEFAULT: 'var(--color-secondary)',
                    light: 'var(--color-secondary-light)',
                },
                surface: {
                    DEFAULT: 'var(--color-surface)',
                    dim: 'var(--color-surface-dim)',
                    bright: 'var(--color-surface-bright)',
                },
                success: {
                    DEFAULT: 'var(--color-success)',
                    container: 'var(--color-success-container)',
                },
                warning: {
                    DEFAULT: 'var(--color-warning)',
                    container: 'var(--color-warning-container)',
                },
                error: {
                    DEFAULT: 'var(--color-error)',
                    container: 'var(--color-error-container)',
                },
            },
        },
    },
}
```

Usage in templates:

```html
{# Uses semantic tokens - works in both light and dark mode #}
<div class="bg-surface text-on-surface border border-outline rounded-lg p-4">
    <h3 class="text-primary font-semibold">{{ essay.title }}</h3>
    <p class="text-on-surface-variant">{{ essay.stage }}</p>
</div>

{# Status badge using semantic colors #}
<span class="bg-success-container text-success px-2 py-0.5 rounded-full text-sm">
    Published
</span>
```

### Content Stage Color Map

Consistent stage colors across the content publishing domain:

| Stage | Color Role | Light Background | Light Text | Dark Background | Dark Text |
|--------|-----------|-----------------|-----------|----------------|----------|
| Published | success | `bg-success-container` | `text-success` | `bg-success-container` | `text-success` |
| Production | info | `bg-info-container` | `text-info` | `bg-info-container` | `text-info` |
| Research | warning | `bg-warning-container` | `text-warning` | `bg-warning-container` | `text-warning` |
| Drafting | neutral | `bg-surface-dim` | `text-on-surface-variant` | `bg-surface-dim` | `text-on-surface-variant` |
| Overdue | error | `bg-error-container` | `text-error` | `bg-error-container` | `text-error` |

## Typography Scale

Define a consistent type scale for headings, body, and UI text:

```css
:root {
    /* Type scale */
    --text-display-lg: 2.25rem;    /* 36px - page titles */
    --text-display-md: 1.875rem;   /* 30px - section titles */
    --text-headline-lg: 1.5rem;    /* 24px - card titles */
    --text-headline-md: 1.25rem;   /* 20px - subsections */
    --text-title-lg: 1.125rem;     /* 18px - list item titles */
    --text-title-md: 1rem;         /* 16px - navigation */
    --text-body-lg: 1rem;          /* 16px - body text */
    --text-body-md: 0.875rem;      /* 14px - secondary text */
    --text-label-lg: 0.875rem;     /* 14px - form labels, buttons */
    --text-label-md: 0.75rem;      /* 12px - badges, captions */

    /* Line heights */
    --leading-tight: 1.25;
    --leading-normal: 1.5;
    --leading-relaxed: 1.75;

    /* Font families */
    --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, monospace;
}
```

Map to Tailwind:

```javascript
theme: {
    extend: {
        fontSize: {
            'display-lg': ['2.25rem', { lineHeight: '1.25' }],
            'display-md': ['1.875rem', { lineHeight: '1.25' }],
            'headline-lg': ['1.5rem', { lineHeight: '1.3' }],
            'headline-md': ['1.25rem', { lineHeight: '1.3' }],
            'title-lg': ['1.125rem', { lineHeight: '1.4' }],
            'body-lg': ['1rem', { lineHeight: '1.5' }],
            'body-md': ['0.875rem', { lineHeight: '1.5' }],
            'label-lg': ['0.875rem', { lineHeight: '1.4', fontWeight: '500' }],
            'label-md': ['0.75rem', { lineHeight: '1.4', fontWeight: '500' }],
        },
    },
}
```

## Spacing System

Use a consistent spacing scale based on a 4px grid:

| Token | Value | Use Case |
|-------|-------|----------|
| `space-1` | 0.25rem (4px) | Inline gaps, icon margins |
| `space-2` | 0.5rem (8px) | Tight padding, small gaps |
| `space-3` | 0.75rem (12px) | Form field padding |
| `space-4` | 1rem (16px) | Standard padding, card body |
| `space-6` | 1.5rem (24px) | Section gaps |
| `space-8` | 2rem (32px) | Large section spacing |
| `space-12` | 3rem (48px) | Page section margins |

Tailwind's default spacing scale already uses a 4px grid (`p-1` = 4px, `p-2` = 8px, etc.), so these map directly.

## Component Token Patterns

Define component-level tokens that reference the global tokens:

```css
:root {
    /* Card component */
    --card-bg: var(--color-surface);
    --card-border: var(--color-outline-variant);
    --card-radius: 0.5rem;
    --card-padding: 1rem;
    --card-shadow: 0 1px 3px rgb(0 0 0 / 0.1);

    /* Button component */
    --btn-radius: 0.375rem;
    --btn-padding-x: 1rem;
    --btn-padding-y: 0.5rem;
    --btn-font-size: var(--text-label-lg);

    /* Input component */
    --input-bg: var(--color-surface);
    --input-border: var(--color-outline);
    --input-border-focus: var(--color-primary);
    --input-radius: 0.375rem;
    --input-padding: 0.5rem 0.75rem;

    /* Table component */
    --table-header-bg: var(--color-surface-dim);
    --table-border: var(--color-outline-variant);
    --table-row-hover: var(--color-surface-dim);
    --table-stripe: var(--color-surface-dim);
}
```

These tokens are consumed by Cotton components (see templates.md):

```html
{# templates/cotton/card.html #}
<c-vars class="" elevated="false" />

<div class="rounded-lg border p-4
            bg-[var(--card-bg)] border-[var(--card-border)]
            {% if elevated %}shadow-lg{% else %}shadow-sm{% endif %}
            {{ class }}"
     {{ attrs }}>
    {{ slot }}
</div>
```

## Material Design 3 Integration

django-material provides pre-built Material Design 3 components with proper token support.

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
{# Material components use the MD3 token system automatically #}
<c-button.filled>Submit Application</c-button.filled>
<c-button.outlined>Cancel</c-button.outlined>
<c-button.text>Learn More</c-button.text>
{% endblock %}
```

### MD3 Color Scheme

Material Design 3 uses a structured color scheme with primary, secondary, tertiary, and error tonal palettes. django-material maps these to CSS custom properties:

```css
/* Material Design 3 color roles */
:root {
    --md-sys-color-primary: #1e40af;
    --md-sys-color-on-primary: #ffffff;
    --md-sys-color-primary-container: #dbeafe;
    --md-sys-color-on-primary-container: #1e3a8a;

    --md-sys-color-secondary: #7c3aed;
    --md-sys-color-on-secondary: #ffffff;

    --md-sys-color-tertiary: #0d9488;
    --md-sys-color-on-tertiary: #ffffff;

    --md-sys-color-error: #dc2626;
    --md-sys-color-on-error: #ffffff;

    --md-sys-color-surface: #ffffff;
    --md-sys-color-on-surface: #111827;
}
```

### Integrating custom themes with MD3

Override Material's CSS custom properties to match your brand:

```css
/* static/css/theme-overrides.css */
:root {
    --md-sys-color-primary: var(--color-primary);
    --md-sys-color-surface: var(--color-surface);
    --md-sys-color-on-surface: var(--color-on-surface);
}
```

This bridges your design system tokens (defined above) with Material's component tokens, so all Material components use your brand colors.

## Theme Switching

### Light/dark toggle with Alpine

```html
<div x-data="{ dark: localStorage.getItem('theme') === 'dark' }"
     x-init="$watch('dark', val => {
         localStorage.setItem('theme', val ? 'dark' : 'light')
         document.documentElement.classList.toggle('dark', val)
     })"
     x-effect="document.documentElement.classList.toggle('dark', dark)">
    <button @click="dark = !dark">
        <span x-show="!dark">Dark Mode</span>
        <span x-show="dark">Light Mode</span>
    </button>
</div>
```

### System preference detection

```html
<script>
    // Apply before page renders to prevent flash
    if (localStorage.theme === 'dark' ||
        (!('theme' in localStorage) &&
         window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark')
    }
</script>
```

Place this script in the `<head>` before any stylesheets load to prevent a flash of unstyled content (FOUC).

## Anti-Patterns

- **Hardcoding hex colors in templates.** Use semantic tokens (`bg-primary`, `text-error`) instead of raw values (`bg-[#1e40af]`). Hardcoded colors break theme switching.
- **Inconsistent spacing.** Pick a spacing scale and stick to it. Mixing `p-3`, `p-[14px]`, and `padding: 0.9rem` in the same project creates visual inconsistency.
- **Defining component styles inline.** Component-level tokens should be in CSS, consumed by Cotton templates. Inline styles cannot be themed.
- **Skipping the dark theme test.** If you define dark mode tokens, test every page in dark mode. Forgotten `dark:` variants leave unreadable white text on white backgrounds.
- **Mixing Material Design with a custom design system.** Either use django-material's full token system or build your own. Overriding half of Material's tokens while keeping the other half creates an inconsistent look.
