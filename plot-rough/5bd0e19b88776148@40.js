function _1(md){return(
md`# Plot: Rough

Adapting Jo Wood’s [Making Plot Sketchy](https://observablehq.com/@jwolondon/making-plot-sketchy) to use a render transform.`
)}

function _2(Plot,barData,rough){return(
Plot.rectY(barData, rough({x: "cat", y: "val", fill: "cat"})).plot()
)}

function _barData(){return(
[
  {cat: "a", val: 4},
  {cat: "b", val: 10},
  {cat: "c", val: 8},
  {cat: "d", val: 6}
]
)}

function _rough(Element,getComputedStyle,roughJS)
{
  // Based on https://observablehq.com/@jwolondon/making-plot-sketchy
  function rough(options) {
    return {
      ...options,
      render(index, scales, values, dimensions, context, next) {
        const node = next(index, scales, values, dimensions, context);
        const elements = node.querySelectorAll([...DRAWABLE_TAGS]);

        for (const el of elements) {
          if (!(el instanceof Element) || el.closest("defs, clipPath")) {
            continue;
          }

          // Read only what is explicitly present on the element or in ancestors
          let effFill = getNearestAttribute(el, "fill");
          let effStroke = getNearestAttribute(el, "stroke");
          const fo = Number.parseFloat(getNearestAttribute(el, "fill-opacity"));
          const so = Number.parseFloat(
            getNearestAttribute(el, "stroke-opacity")
          );
          const sw = Number.parseFloat(getNearestAttribute(el, "stroke-width"));

          // Respect explicit 0-opacity on element: treat as none.
          if (Number.isFinite(fo) && fo <= 0) effFill = "none";
          if (Number.isFinite(so) && so <= 0) effStroke = "none";

          // Geometry-based intent when nothing explicit is provided
          const tag = el.tagName;
          const closed = tag === "path" && isClosedPath(el);
          const isLinearGeom =
            tag === "line" || tag === "polyline" || (tag === "path" && !closed);

          // If both paints are absent/none, infer by geometry to mimic Plot default
          if (isNone(effFill) && isNone(effStroke)) {
            if (tag === "circle" || isLinearGeom) {
              // Plot.dot / lines default: stroke-only, no fill
              effStroke = "black";
              effFill = "none";
            } else {
              // Rects / polygons / closed paths default to fill-only, no stroke
              effFill = "black";
              effStroke = "none";
            }
          }

          // Map effective paint to RoughJS options.
          const fillOpt = isNone(effFill) ? undefined : effFill;
          let strokeOpt = isNone(effStroke) ? "none" : effStroke;
          let strokeWidthOpt =
            strokeOpt !== "none" && Number.isFinite(sw) && sw > 0
              ? sw
              : undefined;
          if (strokeOpt !== "none" && strokeWidthOpt == null) {
            strokeWidthOpt = 1;
          }

          const opts = {
            fill: fillOpt,
            stroke: strokeOpt,
            strokeWidth: strokeWidthOpt
          };

          // Fill-only: ensure visible hachures and no outline.
          if (
            opts.fill !== undefined &&
            (opts.stroke === "none" || isNone(opts.stroke))
          ) {
            if (opts.hachureColor === undefined) {
              opts.hachureColor = opts.fill;
            }
            if (opts.fillWeight === undefined) {
              const w = Number.isFinite(opts.strokeWidth)
                ? opts.strokeWidth
                : 1;
              opts.fillWeight = w > 0 ? w : 1;
            }
            if (opts.fillStyle === undefined) {
              opts.fillStyle = "hachure";
            }
            // Keep a real stroke so RoughJS draws, but make it invisible.
            opts.stroke = "rgba(0, 0, 0, 0)";
            if (!(Number.isFinite(opts.strokeWidth) && opts.strokeWidth > 0)) {
              opts.strokeWidth = 1;
            }
          }

          const roughEl = makeRough(el, opts);
          if (!roughEl) {
            continue;
          }

          for (const attr of [
            "transform",
            "clip-path",
            "mask",
            "filter",
            "opacity"
          ]) {
            const v = el.getAttribute(attr);
            if (v != null) {
              roughEl.setAttribute(attr, v);
            }
          }

          roughEl.setAttribute("aria-hidden", "true");
          roughEl.setAttribute("role", "presentation");
          roughEl.setAttribute("pointer-events", "none");

          el.replaceWith(roughEl);
        }

        return node;
      }
    };
  }

  const DRAWABLE_TAGS = new Set([
    "rect",
    "circle",
    "path",
    "line",
    "polygon",
    "polyline"
  ]);

  // For checking if an element is not present/visible so does not need rough styling
  // Matches "... / 0)" across rgb/rgba/hsl/hsla/color()
  function isNone(v) {
    if (v == null) return true;
    const s = String(v).trim().toLowerCase();
    switch (s) {
      case "":
      case "none":
      case "transparent":
      case "rgba(0, 0, 0, 0)":
      case "rgba(0 0 0 / 0)":
      case "hsla(0, 0%, 0%, 0)":
      case "hsla(0 0% 0% / 0)":
        return true;
    }
    return /\/\s*0\)?$/i.test(s);
  }

  function getNearestAttribute(el, name) {
    let n = el;
    while (n?.nodeType === 1) {
      const v = n.getAttribute(name);
      if (!isNone(v)) {
        if (v.toLowerCase() === "currentcolor") {
          const c = getComputedStyle(n).color;
          return isNone(c) ? undefined : c;
        }
        return v;
      }
      n = n.parentElement;
    }
  }

  // Closed-path detector for geometry-based defaults (bars can render as closed paths if rounded corners)
  function isClosedPath(el) {
    if (el?.tagName?.toLowerCase() !== "path") return false;
    const d = el.getAttribute("d");
    return !!(d && /[Zz]\s*$/.test(d.trim()));
  }

  function parsePoints(points) {
    return points
      .trim()
      .split(/\s+/)
      .map((p) => p.split(",").map(Number));
  }

  const roughCache = new WeakMap();

  function getRough(el) {
    const owner = el.ownerSVGElement ?? el;
    let rough = roughCache.get(owner);
    if (!rough) roughCache.set(owner, rough = roughJS.svg(owner));
    return rough;
  }

  function makeRough(el, opts) {
    const rough = getRough(el);
    switch (el.tagName) {
      case "rect": {
        const x = +el.getAttribute("x") || 0;
        const y = +el.getAttribute("y") || 0;
        const w = +el.getAttribute("width");
        const h = +el.getAttribute("height");
        if (!Number.isFinite(w) || !Number.isFinite(h)) break;
        return rough.rectangle(x, y, w, h, opts);
      }
      case "circle": {
        const cx = +el.getAttribute("cx");
        const cy = +el.getAttribute("cy");
        const r = +el.getAttribute("r");
        if (![cx, cy, r].every(Number.isFinite)) break;
        return rough.circle(cx, cy, 2 * r, opts);
      }
      case "path": {
        const d = el.getAttribute("d");
        if (!d) break;
        return rough.path(d, opts);
      }
      case "line": {
        const x1 = +el.getAttribute("x1");
        const y1 = +el.getAttribute("y1");
        const x2 = +el.getAttribute("x2");
        const y2 = +el.getAttribute("y2");
        if (![x1, y1, x2, y2].every(Number.isFinite)) break;
        return rough.line(x1, y1, x2, y2, opts);
      }
      case "polygon": {
        const pts = el.getAttribute("points");
        if (!pts) break;
        const coords = parsePoints(pts);
        if (!coords.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y))) break;
        return rough.polygon(coords, opts);
      }
      case "polyline": {
        const pts = el.getAttribute("points");
        if (!pts) break;
        const coords = parsePoints(pts);
        if (!coords.every(([x, y]) => Number.isFinite(x) && Number.isFinite(y))) break;
        return rough.linearPath(coords, opts);
      }
    }
  }

  return rough;
}


function _roughJS(){return(
import("https://cdn.jsdelivr.net/npm/roughjs/+esm").then((_) => _.default)
)}

export default function define(runtime, observer) {
  const main = runtime.module();
  main.variable(observer()).define(["md"], _1);
  main.variable(observer()).define(["Plot","barData","rough"], _2);
  main.variable(observer("barData")).define("barData", _barData);
  main.variable(observer("rough")).define("rough", ["Element","getComputedStyle","roughJS"], _rough);
  main.variable(observer("roughJS")).define("roughJS", _roughJS);
  return main;
}
