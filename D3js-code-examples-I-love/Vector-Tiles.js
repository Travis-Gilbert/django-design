map = svg`<svg viewBox="0 0 ${width} ${height}">${tiles.map(d => svg`
  <path fill="#eee" d="${path(filter(d.data.water, d => !d.properties.boundary))}"></path>
  <path fill="none" stroke="#aaa" d="${path(filter(d.data.water, d => d.properties.boundary))}"></path>
  <path fill="none" stroke="#000" stroke-width="0.75" d="${path(d.data.roads)}"></path>
`)}
</svg>`
tiles = Promise.all(tile().map(async d => {
    d.data = await fetch(`https://tile.nextzen.org/tilezen/vector/v1/256/all/${d[2]}/${d[0]}/${d[1]}.json?api_key=YOUR_NEXTZEN_API_KEY`).then(response => response.json());
    return d;
}))
tile = d3.tile()
    .size([width, height])
    .scale(projection.scale() * 2 * Math.PI)
    .translate(projection([0, 0]))
projection = d3.geoMercator()
    .center([-122.4183, 37.7750])
    .scale(Math.pow(2, 21) / (2 * Math.PI))
    .translate([width / 2, height / 2])
function filter({features}, test) {
    return {type: "FeatureCollection", features: features.filter(test)};
}
path = d3.geoPath(projection)
height = 600
d3 = require("d3-geo@3", "d3-tile@1")