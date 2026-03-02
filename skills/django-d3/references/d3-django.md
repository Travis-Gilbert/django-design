# D3.js + Django Reference

D3 (Data-Driven Documents) creates dynamic data visualizations from Django-served data. Django provides the data through template context or API endpoints; D3 renders it as SVG charts in the browser.

## Data Handoff: Django to D3

### json_script filter (template context)

For data already available in the view context, use Django's `json_script` filter. It creates a `<script type="application/json">` tag with properly escaped data.

```python
# apps/content/views.py
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth


def publishing_dashboard(request):
    # Monthly publication data for a line chart
    monthly_data = list(
        Essay.objects.filter(draft=False)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(
            count=Count('id'),
            total_words=Sum('word_count'),
        )
        .order_by('month')
    )

    # Stage breakdown for a bar chart
    stage_data = list(
        Essay.objects.filter(draft=False)
        .values('stage')
        .annotate(count=Count('id'))
        .order_by('stage')
    )

    return render(request, 'content/dashboard.html', {
        'monthly_data': monthly_data,
        'stage_data': stage_data,
    })
```

```html
{# templates/content/dashboard.html #}
{% load static %}

{{ monthly_data|json_script:"monthly-chart-data" }}
{{ stage_data|json_script:"stage-chart-data" }}

<div id="monthly-chart"></div>
<div id="stage-chart"></div>

<script src="https://d3js.org/d3.v7.min.js"></script>
<script src="{% static 'js/charts/monthly-publications.js' %}"></script>
<script src="{% static 'js/charts/stage-breakdown.js' %}"></script>
```

### DRF API endpoints (dynamic data)

For charts that update without page reload, serve data from API endpoints. See api.md for DRF ViewSet patterns.

```python
# apps/content/api_views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def chart_monthly_publications(request):
    """Return monthly essay publication counts for charting."""
    year = request.query_params.get('year', timezone.now().year)
    data = list(
        Essay.objects.filter(date__year=year)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(count=Count('id'), total_words=Sum('word_count'))
        .order_by('month')
    )
    return Response(data)
```

```javascript
// Fetch from API endpoint
async function loadChartData(year) {
    const response = await fetch(`/api/v1/charts/monthly-publications/?year=${year}`)
    const data = await response.json()
    renderMonthlyChart(data)
}
```

**When to use which approach:**
- `json_script`: Data is static for the page load, already in the view context, no user interaction needed.
- API endpoint: Data changes based on user input (date range picker, filter controls), needs periodic refresh, or is shared across multiple pages.

## Bar Chart: Stage Breakdown

```javascript
// static/js/charts/stage-breakdown.js
(function() {
    const data = JSON.parse(
        document.getElementById('stage-chart-data').textContent
    )

    const margin = { top: 20, right: 20, bottom: 40, left: 50 }
    const width = 500 - margin.left - margin.right
    const height = 300 - margin.top - margin.bottom

    const svg = d3.select('#stage-chart')
        .append('svg')
        .attr('viewBox', `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`)
        .attr('class', 'w-full h-auto')  // responsive via CSS
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`)

    // Scales
    const x = d3.scaleBand()
        .domain(data.map(d => d.stage))
        .range([0, width])
        .padding(0.2)

    const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.count)])
        .nice()
        .range([height, 0])

    // Color scale matching content stage semantics
    const color = d3.scaleOrdinal()
        .domain(['published', 'production', 'drafting', 'research'])
        .range(['#16a34a', '#8b5cf6', '#6b7280', '#eab308'])

    // Bars
    svg.selectAll('.bar')
        .data(data)
        .join('rect')
        .attr('class', 'bar')
        .attr('x', d => x(d.stage))
        .attr('y', d => y(d.count))
        .attr('width', x.bandwidth())
        .attr('height', d => height - y(d.count))
        .attr('fill', d => color(d.stage))
        .attr('rx', 4)  // rounded corners

    // Axes
    svg.append('g')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x))
        .selectAll('text')
        .style('text-transform', 'capitalize')

    svg.append('g')
        .call(d3.axisLeft(y).ticks(5))
})()
```

## Line Chart: Monthly Publications

```javascript
// static/js/charts/monthly-publications.js
(function() {
    const raw = JSON.parse(
        document.getElementById('monthly-chart-data').textContent
    )

    // Parse dates from Django's ISO format
    const data = raw.map(d => ({
        month: new Date(d.month),
        count: d.count,
        totalWords: parseInt(d.total_words) || 0,
    }))

    const margin = { top: 20, right: 60, bottom: 40, left: 50 }
    const width = 700 - margin.left - margin.right
    const height = 350 - margin.top - margin.bottom

    const svg = d3.select('#monthly-chart')
        .append('svg')
        .attr('viewBox', `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`)
        .attr('class', 'w-full h-auto')
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`)

    // Scales
    const x = d3.scaleTime()
        .domain(d3.extent(data, d => d.month))
        .range([0, width])

    const y = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.count)])
        .nice()
        .range([height, 0])

    // Line generator
    const line = d3.line()
        .x(d => x(d.month))
        .y(d => y(d.count))
        .curve(d3.curveMonotoneX)

    // Area fill under the line
    const area = d3.area()
        .x(d => x(d.month))
        .y0(height)
        .y1(d => y(d.count))
        .curve(d3.curveMonotoneX)

    svg.append('path')
        .datum(data)
        .attr('fill', '#3b82f6')
        .attr('fill-opacity', 0.1)
        .attr('d', area)

    svg.append('path')
        .datum(data)
        .attr('fill', 'none')
        .attr('stroke', '#3b82f6')
        .attr('stroke-width', 2)
        .attr('d', line)

    // Data points
    svg.selectAll('.dot')
        .data(data)
        .join('circle')
        .attr('cx', d => x(d.month))
        .attr('cy', d => y(d.count))
        .attr('r', 4)
        .attr('fill', '#3b82f6')

    // Axes
    svg.append('g')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x).ticks(d3.timeMonth.every(1)).tickFormat(d3.timeFormat('%b')))

    svg.append('g')
        .call(d3.axisLeft(y).ticks(5))
})()
```

## Force-Directed Graph: Content Network

Useful for visualizing essay-source research networks. Essays link to sources through SourceLink (cross-service slug references), revealing which essays share common research material:

```python
# apps/content/api_views.py
@api_view(['GET'])
def chart_content_network(request):
    """Return nodes and links for a force-directed essay-source graph."""
    essays = Essay.objects.filter(draft=False).prefetch_related('source_links')[:50]

    nodes = []
    links = []
    source_slugs = set()

    for essay in essays:
        nodes.append({
            'id': f'essay-{essay.pk}',
            'label': essay.title[:30],
            'type': 'essay',
            'stage': essay.stage,
        })
        for link in essay.source_links.all():
            if link.content_slug not in source_slugs:
                source_slugs.add(link.content_slug)
                nodes.append({
                    'id': f'source-{link.content_slug}',
                    'label': link.content_slug,
                    'type': 'source',
                })
            links.append({
                'source': f'essay-{essay.pk}',
                'target': f'source-{link.content_slug}',
            })

    return Response({'nodes': nodes, 'links': links})
```

```javascript
// static/js/charts/content-network.js
async function renderContentNetwork(container) {
    const response = await fetch('/api/v1/charts/content-network/')
    const { nodes, links } = await response.json()

    const width = 800
    const height = 600

    const svg = d3.select(container)
        .append('svg')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'w-full h-auto')

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30))

    // Links
    const link = svg.selectAll('.link')
        .data(links)
        .join('line')
        .attr('stroke', '#d1d5db')
        .attr('stroke-width', 1.5)

    // Nodes
    const node = svg.selectAll('.node')
        .data(nodes)
        .join('g')
        .attr('class', 'node')
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended))

    // Node circles: sources are larger (research hubs), essays are smaller
    node.append('circle')
        .attr('r', d => d.type === 'source' ? 12 : 8)
        .attr('fill', d => d.type === 'source' ? '#8b5cf6' : '#3b82f6')

    // Node labels
    node.append('text')
        .text(d => d.label)
        .attr('dx', 15)
        .attr('dy', 4)
        .style('font-size', '11px')
        .style('fill', '#374151')

    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y)

        node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
    }

    function dragged(event, d) {
        d.fx = event.x
        d.fy = event.y
    }

    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0)
        d.fx = null
        d.fy = null
    }
}
```

## Responsive SVG Pattern

All D3 charts should use the `viewBox` pattern for responsive sizing:

```javascript
// DO: responsive SVG
const svg = d3.select('#chart')
    .append('svg')
    .attr('viewBox', `0 0 ${width} ${height}`)
    .attr('class', 'w-full h-auto')

// DON'T: fixed pixel dimensions
const svg = d3.select('#chart')
    .append('svg')
    .attr('width', 800)
    .attr('height', 400)
```

The `viewBox` approach scales the SVG to fit its container. Combined with Tailwind's `w-full h-auto` classes, charts adapt to any screen size.

For charts that need to resize dynamically (e.g., in a resizable panel):

```javascript
function createResponsiveChart(container) {
    const resizeObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
            const { width } = entry.contentRect
            updateChart(width)
        }
    })
    resizeObserver.observe(document.querySelector(container))
}
```

## D3 + Alpine Reactivity

Use Alpine to control D3 chart parameters (date range, filters) and trigger re-renders:

```html
<div x-data="chartController()" x-init="loadData()">
    <div class="flex gap-4 mb-4">
        <select x-model="year" @change="loadData()">
            <option value="2024">2024</option>
            <option value="2025">2025</option>
            <option value="2026">2026</option>
        </select>
        <select x-model="metric" @change="updateChart()">
            <option value="count">Essay Count</option>
            <option value="totalWords">Total Words</option>
        </select>
    </div>
    <div id="interactive-chart" x-ref="chart"></div>
</div>

{{ chart_config|json_script:"chart-config" }}

<script>
function chartController() {
    return {
        year: '2026',
        metric: 'count',
        data: [],
        chart: null,

        async loadData() {
            const response = await fetch(
                `/api/v1/charts/monthly-publications/?year=${this.year}`
            )
            this.data = await response.json()
            this.renderChart()
        },

        renderChart() {
            // Clear previous chart
            d3.select(this.$refs.chart).selectAll('*').remove()
            // Render with current data and metric
            renderMonthlyChart(this.$refs.chart, this.data, this.metric)
        },

        updateChart() {
            this.renderChart()
        },
    }
}
</script>
```

## Template Integration Pattern

Organize chart code for maintainability:

```
static/
    js/
        charts/
            utils.js              # shared: margins, colors, responsive setup
            stage-breakdown.js    # bar chart
            monthly-publications.js  # line chart
            content-network.js    # force-directed graph
            publishing-progress.js  # donut/ring chart
```

```javascript
// static/js/charts/utils.js
export const CHART_COLORS = {
    published: '#16a34a',
    production: '#8b5cf6',
    drafting: '#6b7280',
    research: '#eab308',
    primary: '#3b82f6',
    secondary: '#8b5cf6',
}

export function createSvg(selector, { width = 600, height = 400, margin = {} } = {}) {
    const m = { top: 20, right: 20, bottom: 40, left: 50, ...margin }
    const innerWidth = width - m.left - m.right
    const innerHeight = height - m.top - m.bottom

    const svg = d3.select(selector)
        .append('svg')
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('class', 'w-full h-auto')
        .append('g')
        .attr('transform', `translate(${m.left},${m.top})`)

    return { svg, width: innerWidth, height: innerHeight, margin: m }
}
```

## Anti-Patterns

- **Rendering charts server-side.** Django should provide data, not SVG. D3 runs in the browser where it can handle interactions, animations, and responsive sizing.
- **Passing data via template variables in JavaScript.** Never use `var data = {{ data|safe }}`. Use `json_script` for XSS-safe data transfer.
- **Fixed-size SVGs.** Always use `viewBox` for responsive charts. Pixel-width SVGs break on mobile and in resizable layouts.
- **Loading D3 for simple numbers.** If you just need to display a count or percentage, use a Django template or Alpine. D3 is for complex, interactive visualizations.
- **Rebuilding the entire chart on data change.** Use D3's data join pattern (`.join()`) to update existing elements rather than clearing and redrawing.
- **N+1 queries in chart endpoints.** Chart data endpoints often aggregate across thousands of rows. Use Django annotations (`Count`, `Sum`, `Avg`) and database-level aggregation rather than Python loops. See performance.md for query optimization.
