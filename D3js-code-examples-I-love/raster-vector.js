map = svg`<svg viewBox="0 0 ${width} ${height}">
  ${tile().map(([x, y, z], i, {translate: [tx, ty], scale: k}) => svg`
    <image xlink:href="${url(x, y, z)}" x="${Math.round((x + tx) * k)}" y="${Math.round((y + ty) * k)}" width="${k}" height="${k}">
  `)}
  <path fill="none" stroke="red" d="${path(vectors)}"/>
</svg>`
url = (x, y, z) => `https://api.mapbox.com/styles/v1/mapbox/light-v10/tiles/${z}/${x}/${y}${devicePixelRatio > 1 ? "@2x" : ""}?access_token=YOUR_MAPBOX_ACCESS_TOKEN`
projection = d3.geoMercator()
path = d3.geoPath(projection)
tile = d3.tile()
    .size([width, height])
    .scale(projection.scale() * 2 * Math.PI)
    .translate(projection([0, 0]))
    .tileSize(512)
height = {
    const [[x0, y0], [x1, y1]] = d3.geoPath(projection.fitWidth(width, vectors)).bounds(vectors);
    const height = Math.ceil(y1 - y0);
    const scale = projection.scale() * (2 * Math.PI);
    projection.center(projection.invert([width / 2, height / 2]));
    projection.scale(Math.pow(2, Math.floor(Math.log2(scale))) / (2 * Math.PI));
    projection.translate([width / 2, height / 2]);
    return height;
}
vectors = topojson.feature(topology, topology.objects.detroit)
topology = FileAttachment("detroit.json").json()
d3 = require("d3-geo@3", "d3-tile@1")