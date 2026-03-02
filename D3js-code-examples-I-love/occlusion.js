svg = {
    const width = 928;
    const height = 400;
    const svg = d3
        .create("svg")
        .attr("height", height)
        .attr("viewBox", [0, 0, width, height])
        .attr("style", "max-width: 100%; height: auto; font: 14.5px sans-serif;");
    // Important! Make sure the SVG is attached to the DOM before calling occlusion()
    yield svg.node();
    const n = 1000;
    svg
    .selectAll("text")
        .data(rwg(n))
        .join("text")
        .text((d) => d)
        .attr("x", () => (width * Math.random()) | 0)
        .attr("y", () => (height * Math.random()) | 0);
    let priority = 0;
    svg
    .selectAll("text")
        .on("mouseover", function () {
            d3.select(this).attr("fill", "red").raise();
            svg.call(occlusion);
        })
        .on("mouseout", function () {
            d3.select(this).attr("fill", null);
            svg.call(occlusion);
        })
        .on("click", function () {
            const node = d3.select(this);
            const cur = +node.attr("data-priority");
            node
                .attr("data-priority", cur ? null : ++priority)
                .style("fill", cur ? null : "steelblue");
            svg.call(occlusion);
        });
    do {
        const i = (Math.random() * n) | 0;
        svg.select(`text:nth-of-type(${i})`).raise();
        svg.call(occlusion);
        await Promises.delay(300);
    } while (true);
}
// --- CSS ---
html`<style>
  svg { cursor: pointer; }
  svg text.occluded { opacity: 0.1 }
</style>`
// --- Core occlusion function (importable) ---
function occlusion(svg, against = "text") {
    const nodes = d3
        .sort(svg.selectAll(against), (node) => +node.getAttribute("data-priority"))
        .reverse()
        .map((node) => {
            const { x, y, width, height } = node.getBoundingClientRect();
            return { node, x, y, width, height };
        });
    const visible = [];
    for (const d of nodes) {
        const occluded = visible.some((e) => intersectRect(d, e));
        d3.select(d.node).classed("occluded", occluded);
        if (!occluded) visible.push(d);
    }
    return visible;
}
function intersectRect(a, b) {
    return !(
        a.x + a.width < b.x ||
        b.x + b.width < a.x ||
        a.y + a.height < b.y ||
        b.y + b.height < a.y
    );
}
// --- Random word generator ---
rwg = require("random-words@1.1.0").catch(() => window.words)