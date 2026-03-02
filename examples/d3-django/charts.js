/**
 * D3 + Django Integration: Chart Module
 * ======================================
 *
 * Reusable D3 chart functions for the publishing analytics dashboard.
 * Each function takes a CSS selector for the container and data from
 * the Django API endpoints.
 *
 * Patterns demonstrated:
 *     - Margin convention (top, right, bottom, left)
 *     - Responsive sizing from container dimensions
 *     - Scales: scaleTime, scaleLinear, scaleBand, scaleOrdinal
 *     - Axes with proper formatting
 *     - Data join with .join() (D3 v7 pattern, replaces enter/update/exit)
 *     - Transitions for smooth updates
 *     - Tooltip on hover
 *     - Color scales
 *     - Treemap layout
 *     - ES module-style namespace (attached to window for non-module use)
 *
 * Verify D3 API against:
 *     refs/d3-main/                (D3 source)
 *     refs/plot-main/src/marks/    (Observable Plot marks for comparison)
 */

const PublishingCharts = (function () {
    "use strict";

    // -----------------------------------------------------------------------
    // Shared constants
    // -----------------------------------------------------------------------

    const COLORS = {
        primary: "#3b82f6",   // blue-500
        secondary: "#f59e0b", // amber-500
        muted: "#9ca3af",     // gray-400
        essay: "#3b82f6",
        field_note: "#f59e0b",
        tutorial: "#10b981",
        case_study: "#8b5cf6",
        opinion: "#ef4444",
    };

    const CATEGORY_COLORS = d3.scaleOrdinal()
        .domain(["essay", "tutorial", "case_study", "opinion", "uncategorized"])
        .range(["#3b82f6", "#10b981", "#8b5cf6", "#ef4444", "#9ca3af"]);


    // -----------------------------------------------------------------------
    // Tooltip helper
    // -----------------------------------------------------------------------

    /**
     * Creates or reuses a tooltip div. One tooltip per page, positioned
     * absolutely and shown/hidden via opacity.
     */
    function getTooltip() {
        let tooltip = d3.select("#d3-tooltip");
        if (tooltip.empty()) {
            tooltip = d3.select("body")
                .append("div")
                .attr("id", "d3-tooltip")
                .style("position", "absolute")
                .style("pointer-events", "none")
                .style("background", "rgba(0, 0, 0, 0.8)")
                .style("color", "#fff")
                .style("padding", "6px 10px")
                .style("border-radius", "4px")
                .style("font-size", "12px")
                .style("line-height", "1.4")
                .style("opacity", 0)
                .style("z-index", 9999);
        }
        return tooltip;
    }

    function showTooltip(event, html) {
        const tooltip = getTooltip();
        tooltip
            .html(html)
            .style("opacity", 1)
            .style("left", (event.pageX + 12) + "px")
            .style("top", (event.pageY - 28) + "px");
    }

    function hideTooltip() {
        getTooltip().style("opacity", 0);
    }


    // -----------------------------------------------------------------------
    // 1. Bar Chart: essays per month
    // -----------------------------------------------------------------------

    /**
     * Renders a vertical bar chart inside the given container.
     *
     * @param {string} selector  - CSS selector for the container div
     * @param {Array}  data      - Array of {month: string, count: number}
     *
     * Data shape from Django:
     *     [{"month": "2025-01-01T00:00:00Z", "count": 5}, ...]
     */
    function renderBarChart(selector, data) {
        const container = d3.select(selector);
        const containerNode = container.node();
        if (!containerNode) return;

        // Clear previous chart (for re-renders on parameter change)
        container.selectAll("*").remove();

        // Parse dates if they are strings
        const parsed = data.map(d => ({
            month: d.month instanceof Date ? d.month : new Date(d.month),
            count: d.count,
        }));

        // ---------------------------------------------------------------
        // PATTERN: Margin convention
        //
        // Define margins, then compute the inner drawing area. All scales
        // and drawing use the inner dimensions; the SVG uses the outer.
        // ---------------------------------------------------------------

        const margin = { top: 20, right: 20, bottom: 40, left: 50 };
        const width = containerNode.clientWidth;
        const height = containerNode.clientHeight || width * (9 / 16);
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        // Create SVG with viewBox for responsiveness
        const svg = container.append("svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet")
            .attr("width", "100%")
            .attr("height", "100%");

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        // Scales
        const x = d3.scaleBand()
            .domain(parsed.map(d => d.month))
            .range([0, innerWidth])
            .padding(0.2);

        const y = d3.scaleLinear()
            .domain([0, d3.max(parsed, d => d.count) || 1])
            .nice()
            .range([innerHeight, 0]);

        // Axes
        const xAxis = d3.axisBottom(x)
            .tickFormat(d3.timeFormat("%b %Y"));

        const yAxis = d3.axisLeft(y)
            .ticks(5)
            .tickFormat(d3.format("d"));

        g.append("g")
            .attr("class", "x-axis")
            .attr("transform", `translate(0,${innerHeight})`)
            .call(xAxis)
            .selectAll("text")
            .attr("transform", "rotate(-45)")
            .style("text-anchor", "end")
            .style("font-size", "10px");

        g.append("g")
            .attr("class", "y-axis")
            .call(yAxis);

        // Y-axis label
        g.append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", -margin.left + 15)
            .attr("x", -innerHeight / 2)
            .attr("text-anchor", "middle")
            .style("font-size", "11px")
            .style("fill", "#6b7280")
            .text("Essays published");

        // ---------------------------------------------------------------
        // PATTERN: Data join with .join() (D3 v7)
        //
        // .join() replaces the enter/update/exit pattern. It accepts
        // callbacks for enter, update, and exit, or a single tag name
        // for the simple case.
        //
        // For transitions on update, pass functions:
        //     .join(
        //         enter => enter.append("rect")...,
        //         update => update.transition()...,
        //         exit => exit.transition().attr("height", 0).remove()
        //     )
        // ---------------------------------------------------------------

        g.selectAll(".bar")
            .data(parsed, d => d.month)
            .join(
                enter => enter.append("rect")
                    .attr("class", "bar")
                    .attr("x", d => x(d.month))
                    .attr("width", x.bandwidth())
                    .attr("y", innerHeight)
                    .attr("height", 0)
                    .attr("fill", COLORS.primary)
                    .attr("rx", 2)
                    .on("mouseenter", function (event, d) {
                        d3.select(this).attr("fill", "#2563eb");
                        const label = d3.timeFormat("%B %Y")(d.month);
                        showTooltip(event, `<strong>${label}</strong><br>${d.count} essays`);
                    })
                    .on("mousemove", function (event) {
                        showTooltip(event, getTooltip().html());
                    })
                    .on("mouseleave", function () {
                        d3.select(this).attr("fill", COLORS.primary);
                        hideTooltip();
                    })
                    .call(enter => enter.transition()
                        .duration(600)
                        .delay((d, i) => i * 50)
                        .attr("y", d => y(d.count))
                        .attr("height", d => innerHeight - y(d.count))
                    ),

                update => update
                    .call(update => update.transition()
                        .duration(400)
                        .attr("x", d => x(d.month))
                        .attr("width", x.bandwidth())
                        .attr("y", d => y(d.count))
                        .attr("height", d => innerHeight - y(d.count))
                    ),

                exit => exit
                    .call(exit => exit.transition()
                        .duration(200)
                        .attr("height", 0)
                        .attr("y", innerHeight)
                        .remove()
                    )
            );
    }


    // -----------------------------------------------------------------------
    // 2. Line Chart: same data, different representation
    // -----------------------------------------------------------------------

    /**
     * Renders a line chart as an alternative to the bar chart.
     * Uses the same data shape as renderBarChart.
     */
    function renderLineChart(selector, data) {
        const container = d3.select(selector);
        const containerNode = container.node();
        if (!containerNode) return;

        container.selectAll("*").remove();

        const parsed = data.map(d => ({
            month: d.month instanceof Date ? d.month : new Date(d.month),
            count: d.count,
        }));

        const margin = { top: 20, right: 20, bottom: 40, left: 50 };
        const width = containerNode.clientWidth;
        const height = containerNode.clientHeight || width * (9 / 16);
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const svg = container.append("svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet")
            .attr("width", "100%")
            .attr("height", "100%");

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scaleTime()
            .domain(d3.extent(parsed, d => d.month))
            .range([0, innerWidth]);

        const y = d3.scaleLinear()
            .domain([0, d3.max(parsed, d => d.count) || 1])
            .nice()
            .range([innerHeight, 0]);

        // Axes
        g.append("g")
            .attr("transform", `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x).ticks(6).tickFormat(d3.timeFormat("%b %Y")))
            .selectAll("text")
            .style("font-size", "10px");

        g.append("g")
            .call(d3.axisLeft(y).ticks(5).tickFormat(d3.format("d")));

        // Line generator
        const line = d3.line()
            .x(d => x(d.month))
            .y(d => y(d.count))
            .curve(d3.curveMonotoneX);

        // Area fill under the line
        const area = d3.area()
            .x(d => x(d.month))
            .y0(innerHeight)
            .y1(d => y(d.count))
            .curve(d3.curveMonotoneX);

        g.append("path")
            .datum(parsed)
            .attr("fill", COLORS.primary)
            .attr("fill-opacity", 0.1)
            .attr("d", area);

        // Animated line path
        const path = g.append("path")
            .datum(parsed)
            .attr("fill", "none")
            .attr("stroke", COLORS.primary)
            .attr("stroke-width", 2)
            .attr("d", line);

        // Animate line drawing
        const totalLength = path.node().getTotalLength();
        path
            .attr("stroke-dasharray", `${totalLength} ${totalLength}`)
            .attr("stroke-dashoffset", totalLength)
            .transition()
            .duration(1000)
            .attr("stroke-dashoffset", 0);

        // Data points with tooltips
        g.selectAll(".dot")
            .data(parsed)
            .join("circle")
            .attr("class", "dot")
            .attr("cx", d => x(d.month))
            .attr("cy", d => y(d.count))
            .attr("r", 4)
            .attr("fill", COLORS.primary)
            .attr("stroke", "#fff")
            .attr("stroke-width", 2)
            .on("mouseenter", function (event, d) {
                d3.select(this).attr("r", 6);
                const label = d3.timeFormat("%B %Y")(d.month);
                showTooltip(event, `<strong>${label}</strong><br>${d.count} essays`);
            })
            .on("mouseleave", function () {
                d3.select(this).attr("r", 4);
                hideTooltip();
            });
    }


    // -----------------------------------------------------------------------
    // 3. Treemap: essays by category and tag
    // -----------------------------------------------------------------------

    /**
     * Renders a treemap from hierarchical data.
     *
     * @param {string} selector  - CSS selector for the container div
     * @param {Object} data      - Hierarchical object with name/children/value
     *
     * Data shape from Django:
     *     {
     *         "name": "essays",
     *         "children": [
     *             {
     *                 "name": "tutorial",
     *                 "children": [{"name": "django", "value": 8}, ...]
     *             },
     *             ...
     *         ]
     *     }
     */
    function renderTreemap(selector, data) {
        const container = d3.select(selector);
        const containerNode = container.node();
        if (!containerNode) return;

        container.selectAll("*").remove();

        const width = containerNode.clientWidth;
        const height = containerNode.clientHeight || width;

        // Build hierarchy and compute layout
        const root = d3.hierarchy(data)
            .sum(d => d.value || 0)
            .sort((a, b) => b.value - a.value);

        d3.treemap()
            .size([width, height])
            .padding(2)
            .paddingTop(18)
            .round(true)(root);

        const svg = container.append("svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet")
            .attr("width", "100%")
            .attr("height", "100%");

        // Draw category groups (depth 1)
        const categoryGroups = svg.selectAll(".category")
            .data(root.children || [])
            .join("g")
            .attr("class", "category");

        // Category background
        categoryGroups.append("rect")
            .attr("x", d => d.x0)
            .attr("y", d => d.y0)
            .attr("width", d => d.x1 - d.x0)
            .attr("height", d => d.y1 - d.y0)
            .attr("fill", "none")
            .attr("stroke", "#e5e7eb")
            .attr("stroke-width", 1);

        // Category label
        categoryGroups.append("text")
            .attr("x", d => d.x0 + 4)
            .attr("y", d => d.y0 + 13)
            .style("font-size", "11px")
            .style("font-weight", "600")
            .style("fill", "#374151")
            .text(d => d.data.name);

        // Draw leaf cells (depth 2: individual tags)
        const leaves = svg.selectAll(".leaf")
            .data(root.leaves())
            .join("g")
            .attr("class", "leaf")
            .attr("transform", d => `translate(${d.x0},${d.y0})`);

        leaves.append("rect")
            .attr("width", d => Math.max(0, d.x1 - d.x0))
            .attr("height", d => Math.max(0, d.y1 - d.y0))
            .attr("fill", d => CATEGORY_COLORS(d.parent.data.name))
            .attr("fill-opacity", 0.7)
            .attr("rx", 2)
            .on("mouseenter", function (event, d) {
                d3.select(this).attr("fill-opacity", 1);
                showTooltip(
                    event,
                    `<strong>${d.data.name}</strong><br>` +
                    `Category: ${d.parent.data.name}<br>` +
                    `${d.data.value} essays`
                );
            })
            .on("mousemove", function (event) {
                const tooltip = getTooltip();
                tooltip
                    .style("left", (event.pageX + 12) + "px")
                    .style("top", (event.pageY - 28) + "px");
            })
            .on("mouseleave", function () {
                d3.select(this).attr("fill-opacity", 0.7);
                hideTooltip();
            });

        // Leaf labels (only if cell is large enough)
        leaves.append("text")
            .attr("x", 4)
            .attr("y", 14)
            .style("font-size", "10px")
            .style("fill", "#fff")
            .style("pointer-events", "none")
            .text(d => {
                const cellWidth = d.x1 - d.x0;
                // Only show label if the cell is wide enough
                if (cellWidth < 40) return "";
                return d.data.name;
            });

        // Value labels
        leaves.append("text")
            .attr("x", 4)
            .attr("y", 26)
            .style("font-size", "9px")
            .style("fill", "rgba(255,255,255,0.8)")
            .style("pointer-events", "none")
            .text(d => {
                const cellWidth = d.x1 - d.x0;
                const cellHeight = d.y1 - d.y0;
                if (cellWidth < 40 || cellHeight < 30) return "";
                return d.data.value;
            });
    }


    // -----------------------------------------------------------------------
    // 4. Timeline: publication events scatter plot
    // -----------------------------------------------------------------------

    /**
     * Renders a timeline scatter plot showing individual publication events.
     *
     * @param {string} selector  - CSS selector for the container div
     * @param {Array}  data      - Array of event objects from the API
     *
     * Data shape from Django:
     *     [
     *         {
     *             "date": "2025-06-15T14:30:00Z",
     *             "title": "...",
     *             "type": "essay",
     *             "content_type": "tutorial",
     *             "word_count": 2400,
     *             "tags": ["django", "python"]
     *         },
     *         ...
     *     ]
     */
    function renderTimeline(selector, data) {
        const container = d3.select(selector);
        const containerNode = container.node();
        if (!containerNode) return;

        container.selectAll("*").remove();

        const parsed = data.map(d => ({
            ...d,
            date: new Date(d.date),
        }));

        const margin = { top: 20, right: 30, bottom: 30, left: 50 };
        const width = containerNode.clientWidth;
        const height = containerNode.clientHeight || width * (9 / 21);
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;

        const svg = container.append("svg")
            .attr("viewBox", `0 0 ${width} ${height}`)
            .attr("preserveAspectRatio", "xMidYMid meet")
            .attr("width", "100%")
            .attr("height", "100%");

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        // Scales
        const x = d3.scaleTime()
            .domain(d3.extent(parsed, d => d.date))
            .range([0, innerWidth])
            .nice();

        // Y scale: word count for essays, fixed position for field notes
        const maxWords = d3.max(parsed, d => d.word_count || 0) || 1;
        const y = d3.scaleLinear()
            .domain([0, maxWords])
            .range([innerHeight, 0])
            .nice();

        // Color by type
        const color = d3.scaleOrdinal()
            .domain(["essay", "field_note"])
            .range([COLORS.essay, COLORS.field_note]);

        // Axes
        g.append("g")
            .attr("transform", `translate(0,${innerHeight})`)
            .call(d3.axisBottom(x).ticks(8).tickFormat(d3.timeFormat("%b %Y")))
            .selectAll("text")
            .style("font-size", "10px");

        g.append("g")
            .call(d3.axisLeft(y).ticks(5).tickFormat(d => d > 0 ? d3.format(",")(d) : ""))
            .selectAll("text")
            .style("font-size", "10px");

        // Y-axis label
        g.append("text")
            .attr("transform", "rotate(-90)")
            .attr("y", -margin.left + 15)
            .attr("x", -innerHeight / 2)
            .attr("text-anchor", "middle")
            .style("font-size", "11px")
            .style("fill", "#6b7280")
            .text("Word count");

        // Data points
        g.selectAll(".event-dot")
            .data(parsed)
            .join("circle")
            .attr("class", "event-dot")
            .attr("cx", d => x(d.date))
            .attr("cy", d => {
                // Essays positioned by word count, field notes at bottom
                if (d.type === "essay" && d.word_count) {
                    return y(d.word_count);
                }
                return innerHeight - 5;
            })
            .attr("r", d => d.type === "essay" ? 5 : 3)
            .attr("fill", d => color(d.type))
            .attr("fill-opacity", 0.7)
            .attr("stroke", d => color(d.type))
            .attr("stroke-width", 1)
            .on("mouseenter", function (event, d) {
                d3.select(this)
                    .attr("r", d.type === "essay" ? 8 : 5)
                    .attr("fill-opacity", 1);

                let html = `<strong>${d.title}</strong><br>`;
                html += `${d3.timeFormat("%B %d, %Y")(d.date)}<br>`;
                html += `Type: ${d.type.replace("_", " ")}<br>`;
                if (d.word_count) {
                    html += `Words: ${d3.format(",")(d.word_count)}<br>`;
                }
                if (d.tags && d.tags.length) {
                    html += `Tags: ${d.tags.join(", ")}`;
                }
                showTooltip(event, html);
            })
            .on("mouseleave", function (event, d) {
                d3.select(this)
                    .attr("r", d.type === "essay" ? 5 : 3)
                    .attr("fill-opacity", 0.7);
                hideTooltip();
            });
    }


    // -----------------------------------------------------------------------
    // Public API
    // -----------------------------------------------------------------------

    return {
        renderBarChart,
        renderLineChart,
        renderTreemap,
        renderTimeline,
    };

})();


// Attach to window so non-module scripts can access it.
// If using ES modules, replace this with:
//     export { renderBarChart, renderLineChart, renderTreemap, renderTimeline };
window.PublishingCharts = PublishingCharts;
