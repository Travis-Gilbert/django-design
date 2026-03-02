formatPercentChange = d3.format("+.1%")
formatRatio = {
    const format = d3.format(".2~r");
    return x => format(x) + "×";
}
color3a = {
    const values = [...deaths.values()];
    return d3.scaleLinear()
        .domain([d3.min(values, ([a, b]) => (b - a) / a), 0, d3.max(values, ([a, b]) => (b - a) / a)])
        .range([-1, 0, 1])
        .interpolate((a, b) => a < 0
            ? t => d3.interpolateBlues(1 - t)
            : t => d3.interpolateReds(t));
}
color3b = {
    const values = [...deaths.values()];
    const max = Math.max(-d3.min(values, ([a, b]) => (b - a) / a), d3.max(values, ([a, b]) => (b - a) / a));
    return d3.scaleLinear()
        .domain([-max, 0, max])
        .range([-1, 0, 1])
        .interpolate((a, b) => a < 0
            ? t => d3.interpolateBlues(1 - t)
            : t => d3.interpolateReds(t));
}
color4 = {
    const values = [...deaths.values()];
    const max = Math.max(d3.max(values, ([a, b]) => a / b), d3.max(values, ([a, b]) => b / a));
    return d3.scaleLog()
        .domain([1 / max, 1, max])
        .range([-1, 0, 1])
        .interpolate((a, b) => a < 0
            ? t => d3.interpolateBlues(1 - t)
            : t => d3.interpolateReds(t));
}
import {
    map, legend, names, deaths, format, formatChange, color, color2, d3
} from "@mbostock/mortality-due-to-alcohol-use-disorder"