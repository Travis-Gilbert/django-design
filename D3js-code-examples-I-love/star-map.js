letters = ({alf: "α", bet: "β", gam: "γ", del: "δ", eps: "ε", zet: "ζ", eta: "η", tet: "θ", iot: "ι", kap: "κ", lam: "λ", mu: "μ", nu: "ν", xi: "ξ", omi: "ο", pi: "π", ro: "ρ", sig: "σ", tau: "τ", ups: "υ", phi: "φ", chi: "χ", psi: "ψ", omg: "ω"})
nominative = ({And: "Andromeda", Ant: "Antlia", Aps: "Apus", Aqr: "Aquarius", Aql: "Aquila", Ara: "Ara", Ari: "Aries", Aur: "Auriga", Boo: "Boötes", Cae: "Caelum", Cam: "Camelopardalis", Cnc: "Cancer", CVn: "Canes Venatici", CMa: "Canis Major", CMi: "Canis Minor", Cap: "Capricornus", Car: "Carina", Cas: "Cassiopeia", Cen: "Centaurus", Cep: "Cepheus", Cet: "Cetus", Cha: "Chamaeleon", Cir: "Circinus", Col: "Columba", Com: "Coma Berenices", CrA: "Corona Austrina", CrB: "Corona Borealis", Crv: "Corvus", Crt: "Crater", Cru: "Crux", Cyg: "Cygnus", Del: "Delphinus", Dor: "Dorado", Dra: "Draco", Equ: "Equuleus", Eri: "Eridanus", For: "Fornax", Gem: "Gemini", Gru: "Grus", Her: "Hercules", Hor: "Horologium", Hya: "Hydra", Hyi: "Hydrus", Ind: "Indus", Lac: "Lacerta", Leo: "Leo", LMi: "Leo Minor", Lep: "Lepus", Lib: "Libra", Lup: "Lupus", Lyn: "Lynx", Lyr: "Lyra", Men: "Mensa", Mic: "Microscopium", Mon: "Monoceros", Mus: "Musca", Nor: "Norma", Oct: "Octans", Oph: "Ophiuchus", Ori: "Orion", Pav: "Pavo", Peg: "Pegasus", Per: "Perseus", Phe: "Phoenix", Pic: "Pictor", Psc: "Pisces", PsA: "Piscis Austrinus", Pup: "Puppis", Pyx: "Pyxis", Ret: "Reticulum", Sge: "Sagitta", Sgr: "Sagittarius", Sco: "Scorpius", Scl: "Sculptor", Sct: "Scutum", Ser: "Serpens", Sex: "Sextans", Tau: "Taurus", Tel: "Telescopium", Tri: "Triangulum", TrA: "Triangulum Australe", Tuc: "Tucana", UMa: "Ursa Major", UMi: "Ursa Minor", Vel: "Vela", Vir: "Virgo", Vol: "Volans", Vul: "Vulpecula"})
genitive = ({And: "Andromedae", Ant: "Antliae", Aps: "Apodis", Aqr: "Aquarii", Aql: "Aquilae", Ara: "Arae", Ari: "Arietis", Aur: "Aurigae", Boo: "Boötis", Cae: "Caeli", Cam: "Camelopardalis", Cnc: "Cancri", CVn: "Canum Venaticorum", CMa: "Canis Majoris", CMi: "Canis Minoris", Cap: "Capricorni", Car: "Carinae", Cas: "Cassiopeiae", Cen: "Centauri", Cep: "Cephei", Cet: "Ceti", Cha: "Chamaeleontis", Cir: "Circini", Col: "Columbae", Com: "Comae Berenices", CrA: "Coronae Australis", CrB: "Coronae Borealis", Crv: "Corvi", Crt: "Crateris", Cru: "Crucis", Cyg: "Cygni", Del: "Delphini", Dor: "Doradus", Dra: "Draconis", Equ: "Equulei", Eri: "Eridani", For: "Fornacis", Gem: "Geminorum", Gru: "Gruis", Her: "Herculis", Hor: "Horologii", Hya: "Hydrae", Hyi: "Hydri", Ind: "Indi", Lac: "Lacertae", Leo: "Leonis", LMi: "Leonis Minoris", Lep: "Leporis", Lib: "Librae", Lup: "Lupi", Lyn: "Lyncis", Lyr: "Lyrae", Men: "Mensae", Mic: "Microscopii", Mon: "Monocerotis", Mus: "Muscae", Nor: "Normae", Oct: "Octantis", Oph: "Ophiuchi", Ori: "Orionis", Pav: "Pavonis", Peg: "Pegasi", Per: "Persei", Phe: "Phoenicis", Pic: "Pictoris", Psc: "Piscium", PsA: "Piscis Austrini", Pup: "Puppis", Pyx: "Pyxidis", Ret: "Reticuli", Sge: "Sagittae", Sgr: "Sagittarii", Sco: "Scorpii", Scl: "Sculptoris", Sct: "Scuti", Ser: "Serpentis", Sex: "Sextantis", Tau: "Tauri", Tel: "Telescopii", Tri: "Trianguli", TrA: "Trianguli Australis", Tuc: "Tucanae", UMa: "Ursae Majoris", UMi: "Ursae Minoris", Vel: "Velorum", Vir: "Virginis", Vol: "Volantis", Vul: "Vulpeculae"}map = {
    const width = 954 + 28;
    const height = width;
    const cx = width / 2;
    const cy = height / 2;
    const radius = d3.scaleLinear([6, -1], [0, 8]);
    const outline = d3.geoCircle().radius(90).center([0, 90])();
    const graticule = d3.geoGraticule().stepMinor([15, 10])();
    const projection = d3.geoStereographic()
        .reflectY(true)
        .scale((width - 120) * 0.5)
        .clipExtent([[0, 0], [width, height]])
        .rotate([0, -90])
        .translate([width / 2, height / 2])
        .precision(0.1);
    const path = d3.geoPath(projection);
    const voronoi = d3.Delaunay
        .from(data.map(projection))
        .voronoi([0, 0, width, height]);
    const svg = d3.create("svg")
        .attr("width", width)
        .attr("height", height)
        .attr("viewBox", [0, 0, width, height])
        .attr("style", "display: block; margin: 0 -14px; width: 100%; height: auto; font: 10px sans-serif; color: white; background: radial-gradient(#081f4b 0%, #061616 100%);")
        .attr("text-anchor", "middle")
        .attr("fill", "currentColor");
    svg.append("path")
        .attr("d", path(graticule))
        .attr("fill", "none")
        .attr("stroke", "currentColor")
        .attr("stroke-opacity", 0.2);
    svg.append("path")
        .attr("d", path(outline))
        .attr("fill", "none")
        .attr("stroke", "currentColor");
    svg.append("g")
        .attr("stroke", "currentColor")
        .selectAll()
        .data(d3.range(0, 1440, 5))
        .join("line")
        .datum(d => [
            projection([d / 4, 0]),
            projection([d / 4, d % 60 ? -1 : -2])
        ])
        .attr("x1", ([[x1]]) => x1)
        .attr("x2", ([, [x2]]) => x2)
        .attr("y1", ([[, y1]]) => y1)
        .attr("y2", ([, [, y2]]) => y2);
    svg.append("g")
        .selectAll()
        .data(d3.range(0, 1440, 60))
        .join("text")
        .attr("dy", "0.35em")
        .text(d => `${d / 60}h`)
        .attr("font-size", d => d % 360 ? null : 14)
        .attr("font-weight", d => d % 360 ? null : "bold")
        .datum(d => projection([d / 4, -4]))
        .attr("x", ([x]) => x)
        .attr("y", ([, y]) => y);
    svg.append("g")
        .selectAll()
        .data(d3.range(10, 91, 10))
        .join("text")
        .attr("dy", "0.35em")
        .text(d => `${d}°`)
        .datum(d => projection([0, d]))
        .attr("x", ([x]) => x)
        .attr("y", ([, y]) => y);
    const focusDeclination = svg.append("circle")
        .attr("cx", cx).attr("cy", cy)
        .attr("fill", "none").attr("stroke", "yellow");
    const focusRightAscension = svg.append("line")
        .attr("x1", cx).attr("y1", cy).attr("x2", cx).attr("y2", cy)
        .attr("stroke", "yellow");
    svg.append("g")
        .attr("stroke", "black")
        .selectAll()
        .data(data)
        .join("circle")
        .attr("r", d => radius(d.magnitude))
        .attr("transform", d => `translate(${projection(d)})`);
    svg.append("g")
        .attr("pointer-events", "all")
        .attr("fill", "none")
        .selectAll()
        .data(data)
        .join("path")
        .on("mouseover", mouseovered)
        .on("mouseout", mouseouted)
        .attr("d", (d, i) => voronoi.renderCell(i))
        .append("title")
        .text(formatTitle);
    function mouseovered()