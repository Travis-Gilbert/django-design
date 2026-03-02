---
name: django-d3
description: Use when the user asks about D3.js charts, data visualization, Observable Plot, SVG rendering, bar charts, line charts, force-directed graphs, data endpoints for charts, json_script filter, responsive SVG, or integrating D3 with Django templates and Alpine.js.
version: 4.0.0
---

# Django D3: Data Visualization with D3.js and Observable Plot

This skill covers building data visualizations in Django projects using D3.js, Observable Plot, and related tools. It addresses the full pipeline: Django data endpoints, safe data handoff to the browser, chart rendering, responsive SVG, and interactive features with Alpine.js.

## Reference Library

- **`references/d3-django.md`** -- Data handoff (json_script filter vs API endpoints), bar charts, line charts, force-directed graphs, responsive SVG, D3 + Alpine reactivity, chart file organization

## Data Handoff: Django to Browser

Two approaches for getting Django data into D3:

### Template Context with json_script (Simple)

For data that is available at page render time:

```html
{{ chart_data|json_script:"chart-data" }}
<script type="module">
  const data = JSON.parse(document.getElementById("chart-data").textContent);
  // D3 rendering here
</script>
```

Never use `{{ data|safe }}` in script tags. The `json_script` filter escapes content properly to prevent XSS.

### API Endpoints (Dynamic)

For data that updates without page reload, or for large datasets:

```python
# views.py
from django.http import JsonResponse

def chart_data_api(request):
    data = MyModel.objects.values("date", "count")
    return JsonResponse(list(data), safe=False)
```

Pair with `fetch()` or HTMX for dynamic loading.

## Chart Organization

```
static/
    js/
        charts/
            utils.js       # shared: margins, color scales, responsive helpers
            bar-chart.js   # bar chart module
            line-chart.js  # line chart module
            force-graph.js # force-directed graph module
```

Each chart module exports a render function that accepts a container selector and data:

```javascript
export function renderBarChart(selector, data, options = {}) {
  const { width, height, margin } = getChartDimensions(selector, options);
  // D3 rendering
}
```

## Key Patterns

### Responsive SVG

Always use `viewBox` instead of fixed pixel dimensions:

```javascript
const svg = d3.select(selector)
  .append("svg")
  .attr("viewBox", `0 0 ${width} ${height}`)
  .attr("preserveAspectRatio", "xMidYMid meet");
```

### Alpine.js Integration

Use Alpine to control chart parameters (date range, filters) while D3 handles rendering:

```html
<div x-data="chartController()" x-init="loadChart()">
  <select x-model="metric" @change="updateChart()">
    <option value="views">Views</option>
    <option value="engagement">Engagement</option>
  </select>
  <div id="chart-container"></div>
</div>
```

### Color Scales

Use D3's built-in color scales or map semantic design tokens:

```javascript
// D3 categorical scale
const color = d3.scaleOrdinal(d3.schemeTableau10);

// Or map from CSS custom properties
const primary = getComputedStyle(document.documentElement)
  .getPropertyValue("--color-primary").trim();
```

## Anti-Patterns

- **Fixed-size SVG charts.** Always use `viewBox` for responsive behavior. Pixel-width SVGs break on mobile.
- **`{{ data|safe }}` in script tags.** Use `json_script` filter. Always.
- **One monolithic chart file.** Split chart types into separate modules with a shared utils file.
- **Rebuilding the entire SVG on data updates.** Use D3's enter/update/exit pattern or Observable Plot's reactive rendering.
- **No loading states.** Show a skeleton or spinner while data loads from API endpoints.

## Agents

| Agent | Focus |
|-------|-------|
| `data-specialist` | D3 charts, Observable Plot, data endpoints, Django-to-D3 integration |
