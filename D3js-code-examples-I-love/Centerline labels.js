places = d3.json("https://gist.githubusercontent.com/veltman/644f16a90259a20a88b036ef189d71fd/raw/d2f0a027bfc9b63ca223b509bd2cfe0cf5d138c2/places.geojson")
feature = places.features.find(f => f.properties.name === place)
projection = d3.geoIdentity().fitExtent([[5, 5], [width - 5, height - 5]], feature)
background = d3.geoPath().projection(projection)(feature)
height = Math.min(width / 2, 400)
outerRing = {
    const s = projection.scale(), t = projection.translate();
    return feature.geometry.coordinates[0][0]
        .slice(1)
        .map(point => [s * point[0] + t[0], s * point[1] + t[1]]);
}
polygon = getPointsAlongPolyline(outerRing, numPerimeterPoints)
voronoi = {
    const [x0, x1] = d3.extent(polygon.map(d => d[0])),
    [y0, y1] = d3.extent(polygon.map(d => d[1]));
return d3.voronoi().extent([[x0 - 1, y0 - 1], [x1 + 1, y1 + 1]])(polygon).edges;
}
// Edge clipping to polygon boundary
edges = voronoi
    .filter(edge => {
        if (edge && edge.right) {
            const inside = edge.map(point => d3.polygonContains(polygon, point));
            if (inside[0] === inside[1]) return inside[0];
            if (inside[1]) edge.reverse();
            return true;
        }
        return false;
    })
    .map(([start, end] = []) => {
        const { intersection, distance } = findClosestPolygonIntersection(start, end, polygon);
        if (intersection) intersection.clipped = true;
        const edge = [start, intersection || end];
        edge.distance = intersection ? distance : distanceBetween(start, end);
        return edge;
    })
// Graph construction from nodes
nodes = {
    const nodes = [];
    edges.forEach(edge => {
        edge.forEach((node, i) => {
            if (!i || !node.clipped) {
                const match = nodes.find(d => d === node);
                if (match) return (node.id = match.id);
            }
            node.id = nodes.length.toString();
            node.links = {};
            nodes.push(node);
        });
        edge[0].links[edge[1].id] = edge.distance;
        edge[1].links[edge[0].id] = edge.distance;
    });
    return nodes;
}
perimeterNodes = nodes.filter(d => d.clipped)
graph = {
    const graph = new Graph();
    nodes.forEach(node => graph.addNode(node.id, node.links));
    return graph;
}
// Best path traversal (Dijkstra on all perimeter node pairs)
traversal = {
    let totalBest;
    for (let i = 0; i < perimeterNodes.length; i++) {
    const start = perimeterNodes[i];
    const longestShortestPath = perimeterNodes.slice(i + 1).reduce((nodeBest, node) => {
        const path = graph.path(node.id, start.id, { cost: true });
        if (path && (!nodeBest || path.cost > nodeBest.cost)) return path;
        return nodeBest;
    }, null);
    if (longestShortestPath && longestShortestPath.path) {
        longestShortestPath.path = longestShortestPath.path.map(id => nodes[+id]);
        longestShortestPath.cost = fitnessFunction(longestShortestPath.path, longestShortestPath.cost);
        if (!totalBest || longestShortestPath.cost > totalBest.cost) totalBest = longestShortestPath;
        yield Promises.delay(+speed, { bestPath: totalBest.path, currentPath: longestShortestPath.path });
    }
}
if (totalBest) yield { bestPath: totalBest.path };
}
simplifiedLine = simplify(traversal.bestPath)
centerline = d3.line().curve(d3.curveBasis)(flipText ? simplifiedLine.slice(0).reverse() : simplifiedLine)
// --- Helper functions ---
function fitnessFunction(path, length) { /* ... factors in sinuosity */ }
function findClosestPolygonIntersection(start, end, polygon) { /* ... */ }
function getPointsAlongPolyline(polyline, count) { /* ... */ }
function findIntersection(a1, a2, b1, b2) { /* ... */ }
function rotatePoint(point, angle, center) { /* ... */ }
function tangentAt(el, len) { /* ... */ }
function distanceBetween(a, b) { /* ... */ }
// Graph class: full Dijkstra implementation (node-dijkstra port)
simplifyJS = require("simplify-js")
d3 = require("d3@5")
import {slider, radio} from "@jashkenas/inputs"