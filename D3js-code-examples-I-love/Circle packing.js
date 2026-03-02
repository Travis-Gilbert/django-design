chart = {
    const width = 928;
    const height = width;
    const margin = 1;
    const format = d3.format(",d");
    const pack = d3.pack()
        .size([width - margin * 2, height - margin * 2])
        .padding(3);
    const root = pack(d3.hierarchy(data)
        .sum(d => d.value)
        .sort((a, b) => b.value - a.value));
    const svg = d3.create("svg")
        .attr("width", width)
        .attr("height", height)
        .attr("viewBox", [-margin, -margin, width, height])
        .attr("style", "width: 100%; height: auto; font: 10px sans-serif;")
        .attr("text-anchor", "middle");
    const node = svg.append("g")
        .selectAll()
        .data(root.descendants())
        .join("g")
        .attr("transform", d => `translate(${d.x},${d.y})`);
    node.append("title")
        .text(d => `${d.ancestors().map(d => d.data.name).reverse().join("/")}\\n${format(d.value)}`);
    node.append("circle")
        .attr("fill", d => d.children ? "#fff" : "#ddd")
        .attr("stroke", d => d.children ? "#bbb" : null)
        .attr("r", d => d.r);
    const text = node
        .filter(d => !d.children && d.r > 10)
        .append("text")
        .attr("clip-path", d => `circle(${d.r})`);
    text.selectAll()
        .data(d => d.data.name.split(/(?=[A-Z][a-z])|\\s+/g))
        .join("tspan")
        .attr("x", 0)
        .attr("y", (d, i, nodes) => `${i - nodes.length / 2 + 0.35}em`)
        .text(d => d);
    text.append("tspan")
        .attr("x", 0)
        .attr("y", d => `${d.data.name.split(/(?=[A-Z][a-z])|\\s+/g).length / 2 + 0.35}em`)
        .attr("fill-opacity", 0.7)
        .text(d => format(d.value));
    return svg.node();
}
// --- Data ---
data = FileAttachment("flare-2.json").json()