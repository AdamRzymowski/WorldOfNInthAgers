import { MAP_IMAGE, LANDMARKS, toImage, wrapLongitude, spansDateline, fitSpline } from "./calibration.js";
import { linkInfo, safeUrl } from "./links.js";
import { loadHitmap } from "./hitmap.js";
import { setupJoin } from "./join.js";

const DEBUG = new URLSearchParams(location.search).has("debug");
const { width: W, height: H } = MAP_IMAGE;

const [topology, communityData, hitmap, countryMaps] = await Promise.all([
  d3.json("data/countries-50m.json"),
  d3.json("data/communities.json"),
  loadHitmap(),
  d3.json("data/country-maps/index.json").catch(() => ({})),
]);

const countries = topojson
  .feature(topology, topology.objects.countries)
  .features.filter((f) => f.properties.name !== "Antarctica");

const byName = new Map(countries.map((f) => [normalize(f.properties.name), f]));
const communitiesByCountry = new Map(
  Object.entries(communityData.countries ?? {}).map(([name, list]) => [normalize(name), list])
);

for (const name of communitiesByCountry.keys()) {
  if (!byName.has(name)) console.warn(`communities.json: no country on the map is called "${name}"`);
}

function normalize(name) {
  return name.trim().toLowerCase();
}

function communitiesFor(feature) {
  return communitiesByCountry.get(normalize(feature.properties.name)) ?? [];
}

// The country's main landmass: its largest polygon plus anything nearby, so
// overseas territories (French Guiana, Hawaii...) don't shrink the view.
function mainland(feature) {
  if (feature.geometry.type !== "MultiPolygon") return feature;
  const polygons = feature.geometry.coordinates.map((coordinates) => ({
    type: "Polygon",
    coordinates,
  }));
  const largest = d3.greatest(polygons, (p) => d3.geoArea(p));
  const center = d3.geoCentroid(largest);
  const near = polygons.filter((p) => d3.geoDistance(center, d3.geoCentroid(p)) < (25 * Math.PI) / 180);
  return {
    type: "Feature",
    properties: feature.properties,
    geometry: { type: "MultiPolygon", coordinates: near.map((p) => p.coordinates) },
  };
}

function labelPoint(feature) {
  const land = mainland(feature);
  const polygons =
    land.geometry.type === "Polygon"
      ? [land.geometry]
      : land.geometry.coordinates.map((coordinates) => ({ type: "Polygon", coordinates }));
  return d3.geoCentroid(d3.greatest(polygons, (p) => d3.geoArea(p)));
}

/* ---------------------------------------------------------------- world map */

const worldSvg = d3.select("#world-map").attr("viewBox", `0 0 ${W} ${H}`);
const stage = worldSvg.append("g");
const tooltip = document.getElementById("tooltip");
const frame = document.querySelector(".world-frame");

stage
  .append("image")
  .attr("href", MAP_IMAGE.src)
  .attr("width", W)
  .attr("height", H)
  .attr("preserveAspectRatio", "none");

function toMap(feature, [lon, lat]) {
  feature.wraps ??= spansDateline(feature);
  return toImage(wrapLongitude(lon, feature.properties.name, feature.wraps), lat);
}

function imagePath(feature) {
  return d3.geoPath(
    d3.geoTransform({
      point(lon, lat) {
        const [x, y] = toMap(feature, [lon, lat]);
        this.stream.point(x, y);
      },
    })
  );
}

// Tint the countries that have communities, using their shapes as drawn.
// With ?debug, tint every country so the hit map can be checked by eye.
const DEBUG_COLOURS = [[230, 25, 75], [60, 180, 75], [0, 130, 200], [245, 130, 48], [145, 30, 180], [70, 200, 200], [240, 50, 230]];
const tints = stage.append("g").attr("class", "tints");
countries.forEach((f, i) => {
  if (!DEBUG && !communitiesFor(f).length) return;
  const c = DEBUG ? DEBUG_COLOURS[i % DEBUG_COLOURS.length] : [200, 151, 62];
  const m = hitmap.mask(f.properties.name, { fill: [...c, DEBUG ? 110 : 60], edge: [...c, DEBUG ? 230 : 60] });
  if (m) tints.append("image").attr("href", m.href).attr("x", m.x).attr("y", m.y).attr("width", m.width).attr("height", m.height);
});

const highlight = stage
  .append("image")
  .attr("class", "highlight")
  .attr("preserveAspectRatio", "none")
  .attr("visibility", "hidden");

// The outlines are invisible: they give keyboard and screen reader users
// something to tab through. Mouse and touch use the hit map so hover follows
// the borders as drawn.
stage
  .append("g")
  .attr("class", "countries")
  .selectAll("path")
  .data(countries)
  .join("path")
  .attr("class", "country")
  .attr("d", (f) => imagePath(f)(f))
  .attr("tabindex", 0)
  .attr("role", "button")
  .attr("aria-label", (f) => {
    const n = communitiesFor(f).length;
    return `${f.properties.name}${n ? `, ${n} ${n === 1 ? "community" : "communities"}` : ""}`;
  })
  .on("focus", (event, f) => {
    setHover(f);
    const [x, y] = d3.zoomTransform(worldSvg.node()).apply(sealPoint(f));
    const box = worldSvg.node().getBoundingClientRect();
    showTooltip(f, box.left + (x / W) * box.width, box.top + (y / H) * box.height);
  })
  .on("blur", () => setHover(null))
  .on("keydown", (event, f) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openCountry(f);
    }
  });

function featureAt(event) {
  const [x, y] = d3.pointer(event, stage.node());
  const name = hitmap.nameAt(x, y);
  return name ? byName.get(normalize(name)) : null;
}

let hovered = null;

function setHover(f) {
  if (f === hovered) return;
  hovered = f;
  const m = f && hitmap.mask(f.properties.name);
  if (!m) {
    highlight.attr("visibility", "hidden");
    hideTooltip();
  } else {
    highlight
      .attr("href", m.href)
      .attr("x", m.x)
      .attr("y", m.y)
      .attr("width", m.width)
      .attr("height", m.height)
      .attr("visibility", "visible");
  }
  worldSvg.classed("over-country", !!f);
}

worldSvg
  .on("pointermove", (event) => {
    const f = featureAt(event);
    setHover(f);
    if (f) showTooltip(f, event.clientX, event.clientY);
  })
  .on("pointerleave", () => setHover(null))
  .on("click", (event) => {
    const f = featureAt(event);
    if (f) openCountry(f);
  });

// "Want to put yourself on the map?": the plus button asks for a country first.
const joinButton = document.getElementById("join-button");
const joinHint = document.getElementById("join-hint");

function setJoining(on) {
  joinButton.setAttribute("aria-pressed", String(on));
  joinHint.hidden = !on;
}

joinButton.addEventListener("click", () => setJoining(joinButton.getAttribute("aria-pressed") !== "true"));
joinHint.querySelector("[data-join-cancel]").addEventListener("click", () => setJoining(false));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !joinHint.hidden) setJoining(false);
});

function sealPoint(f) {
  return hitmap.labelPoints[f.properties.name] ?? toMap(f, labelPoint(f));
}

const seals = stage
  .append("g")
  .attr("class", "seals")
  .selectAll("g")
  .data(countries.filter((f) => communitiesFor(f).length))
  .join("g")
  .attr("class", "seal")
  .each(function (f) {
    f.seal = sealPoint(f);
  })
  .on("click", (event, f) => {
    event.stopPropagation();
    openCountry(f);
  });

seals.append("circle").attr("r", 13);
seals
  .append("text")
  .attr("dy", "0.35em")
  .text((f) => communitiesFor(f).length);

if (DEBUG) {
  stage
    .append("g")
    .attr("class", "landmarks")
    .selectAll("circle")
    .data(LANDMARKS)
    .join("circle")
    .attr("cx", (d) => d[2])
    .attr("cy", (d) => d[3])
    .attr("r", 3)
    .append("title")
    .text((d) => `${d[0]}, ${d[1]}`);
}

function placeSeals(k) {
  seals.attr("transform", (f) => `translate(${f.seal[0]},${f.seal[1]}) scale(${1 / Math.sqrt(k)})`);
}

const worldZoom = d3
  .zoom()
  .scaleExtent([1, 8])
  .translateExtent([
    [0, 0],
    [W, H],
  ])
  .clickDistance(6)
  .on("zoom", ({ transform }) => {
    stage.attr("transform", transform);
    placeSeals(transform.k);
    setHover(null);
  });

worldSvg.call(worldZoom);
placeSeals(1);

document.querySelectorAll("[data-zoom]").forEach((button) =>
  button.addEventListener("click", () => {
    const action = button.dataset.zoom;
    const t = worldSvg.transition().duration(350);
    if (action === "in") worldZoom.scaleBy(t, 1.6);
    else if (action === "out") worldZoom.scaleBy(t, 1 / 1.6);
    else worldZoom.transform(t, d3.zoomIdentity);
  })
);

function showTooltip(f, clientX, clientY) {
  const n = communitiesFor(f).length;
  tooltip.textContent = n
    ? `${f.properties.name} — ${n} ${n === 1 ? "community" : "communities"}`
    : f.properties.name;
  tooltip.hidden = false;

  const box = frame.getBoundingClientRect();
  const x = clientX - box.left;
  tooltip.style.left = `${Math.min(Math.max(x, 60), box.width - 60)}px`;
  tooltip.style.top = `${clientY - box.top}px`;
}

function hideTooltip() {
  tooltip.hidden = true;
}

/* ------------------------------------------------------------- search form */

const datalist = document.getElementById("country-names");
for (const name of countries.map((f) => f.properties.name).sort((a, b) => a.localeCompare(b))) {
  datalist.append(new Option(name));
}

document.getElementById("country-search").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("country-input");
  const feature = byName.get(normalize(input.value));
  if (feature) {
    openCountry(feature);
    input.value = "";
  } else {
    input.setCustomValidity("No country by that name on the map");
    input.reportValidity();
    input.addEventListener("input", () => input.setCustomValidity(""), { once: true });
  }
});

/* ---------------------------------------------------------- country dialog */

let CW = 800; // size of the country map's drawing area (changes for minimaps)
let CH = 560;
const MARKER_R = 48;

const dialog = document.getElementById("country-dialog");
const title = document.getElementById("country-title");
const listEl = document.getElementById("community-list");
const emptyEl = document.getElementById("community-empty");
const card = document.getElementById("community-card");
const countrySvg = d3.select("#country-map").attr("viewBox", `0 0 ${CW} ${CH}`);
const mapWrap = document.querySelector(".country-map-wrap");

const defs = countrySvg.append("defs");
const mapLayer = countrySvg.append("g").attr("class", "country-layer");
const markerLayer = countrySvg.append("g").attr("class", "marker-layer");

let current = null; // { feature, list, projection, nodes }
let lastTransform = d3.zoomIdentity;
let cardNode = null; // marker the community card is pinned to

const countryZoom = d3
  .zoom()
  .scaleExtent([1, 16])
  .translateExtent([
    [0, 0],
    [CW, CH],
  ])
  .clickDistance(6)
  .on("start", ({ sourceEvent }) => {
    if (sourceEvent) closeCard();
  })
  .on("zoom", ({ transform }) => {
    lastTransform = transform;
    mapLayer.attr("transform", transform);
    layoutMarkers();
  });

countrySvg.call(countryZoom);

const join = setupJoin({ countrySvg, mapLayer, mapWrap, getCurrent: () => current, getCanvasWidth: () => CW });

function setCanvas(width, height) {
  CW = width;
  CH = height;
  countrySvg.attr("viewBox", `0 0 ${CW} ${CH}`).style("aspect-ratio", `${CW} / ${CH}`);
  countryZoom.translateExtent([
    [0, 0],
    [CW, CH],
  ]);
}

// Ornate per-country minimaps (data/country-maps/), loaded the first time they're needed.
const minimapCache = new Map();
function loadMinimap(name) {
  const base = countryMaps[name];
  if (!base) return null;
  if (!minimapCache.has(name)) {
    minimapCache.set(
      name,
      Promise.all([d3.json(`${base}.json`), loadHitmap(`${base}-hitmap`)]).then(([config, hits]) => ({
        config,
        hits,
        toMap: fitSpline(config.landmarks ?? hits.landmarks, 5),
      }))
    );
  }
  return minimapCache.get(name);
}

async function openCountry(feature) {
  setHover(null);
  // Arrived through "Want to put yourself on the map?": go straight to planting.
  const plantNow = joinButton.getAttribute("aria-pressed") === "true";
  setJoining(false);
  join.reset();
  closeCard();
  const list = communitiesFor(feature);
  title.textContent = feature.properties.name;
  countrySvg.attr("aria-label", `Map of ${feature.properties.name}`);
  renderList(list);
  if (!dialog.open) dialog.showModal();
  history.replaceState(null, "", `#${encodeURIComponent(feature.properties.name)}`);
  const minimap = await loadMinimap(feature.properties.name)?.catch((err) => {
    console.warn(`Could not load the ${feature.properties.name} minimap`, err);
    return null;
  });
  if (minimap) drawMinimap(feature, list, minimap);
  else drawCountry(feature, list);
  if (plantNow) join.start();
}

// Map coordinates back to longitude/latitude on a minimap: Newton's method on
// the landmark spline, starting from the country's middle.
function invertSpline(toMap, x, y, [lon, lat]) {
  const h = 0.01;
  for (let i = 0; i < 40; i++) {
    const [px, py] = toMap(lon, lat);
    const ex = px - x;
    const ey = py - y;
    if (Math.hypot(ex, ey) < 0.05) break;
    const [ax, ay] = toMap(lon + h, lat);
    const [bx, by] = toMap(lon, lat + h);
    const j00 = (ax - px) / h, j01 = (bx - px) / h;
    const j10 = (ay - py) / h, j11 = (by - py) / h;
    const det = j00 * j11 - j01 * j10;
    if (!det) break;
    lon -= (j11 * ex - j01 * ey) / det;
    lat -= (-j10 * ex + j00 * ey) / det;
  }
  return [lon, lat];
}

function drawMinimap(feature, list, minimap) {
  const { config, hits, toMap } = minimap;
  setCanvas(hits.width, hits.height);

  // Only the community markers are interactive here, not the countries.
  mapLayer.selectAll("*").remove();
  mapLayer.append("image").attr("href", config.image).attr("width", CW).attr("height", CH);

  const middle = d3.geoCentroid(mainland(feature));
  current = {
    feature,
    list,
    minimap,
    fromMap: (x, y) => invertSpline(toMap, x, y, middle),
    contains: (x, y) => hits.nameAt(x, y) === config.country,
    nodes: list
      .filter((c) => Number.isFinite(c.lon) && Number.isFinite(c.lat))
      .map((community, i) => ({ community, index: i, anchor: toMap(community.lon, community.lat) })),
  };
  drawMarkers();
  countrySvg.call(countryZoom.transform, d3.zoomIdentity);
}

function drawCountry(feature, list) {
  setCanvas(800, 560);
  const land = mainland(feature);
  const [centerLon] = d3.geoCentroid(land);
  const points = list
    .filter((c) => Number.isFinite(c.lon) && Number.isFinite(c.lat))
    .map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: [c.lon, c.lat] } }));

  const projection = d3
    .geoMercator()
    .rotate([-centerLon, 0])
    .fitExtent(
      [
        [50, 50],
        [CW - 50, CH - 50],
      ],
      { type: "FeatureCollection", features: [land, ...points] }
    );
  const path = d3.geoPath(projection);

  mapLayer.selectAll("*").remove();
  mapLayer.append("rect").attr("class", "sea").attr("width", CW).attr("height", CH);
  mapLayer.append("path").attr("class", "graticule").attr("d", path(d3.geoGraticule().step([5, 5])()));
  mapLayer
    .append("g")
    .selectAll("path")
    .data(countries.filter((f) => f !== feature))
    .join("path")
    .attr("class", "neighbour")
    .attr("d", path);
  mapLayer.append("path").attr("class", "chosen").attr("d", path(feature));

  current = {
    feature,
    list,
    fromMap: (x, y) => projection.invert([x, y]),
    contains: (x, y) => d3.geoContains(feature, projection.invert([x, y])),
    nodes: list
      .filter((c) => Number.isFinite(c.lon) && Number.isFinite(c.lat))
      .map((community, i) => ({ community, index: i, anchor: projection([community.lon, community.lat]) })),
  };

  drawMarkers();
  countrySvg.call(countryZoom.transform, d3.zoomIdentity);
}

function drawMarkers() {
  defs.selectAll("*").remove();
  markerLayer.selectAll("*").remove();

  const groups = markerLayer
    .selectAll("g.marker")
    .data(current.nodes)
    .join("g")
    .attr("class", "marker");

  groups.append("line").attr("class", "leader");
  groups.append("circle").attr("class", "anchor").attr("r", 3);

  const badge = groups
    .append("g")
    .attr("class", "badge")
    .attr("tabindex", 0)
    .attr("role", "button")
    .attr("aria-label", (d) => d.community.name)
    .on("click", (event, d) => {
      event.stopPropagation();
      openCard(d);
    })
    .on("keydown", (event, d) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openCard(d);
      }
    });

  badge.append("circle").attr("class", "badge-ring").attr("r", MARKER_R + 5);
  badge.each(function (d, i) {
    const g = d3.select(this);
    if (d.community.logo) {
      const id = `logo-clip-${i}`;
      defs.append("clipPath").attr("id", id).append("circle").attr("r", MARKER_R);
      g.append("circle").attr("class", "badge-bg").attr("r", MARKER_R);
      g.append("image")
        .attr("href", d.community.logo)
        .attr("x", -MARKER_R)
        .attr("y", -MARKER_R)
        .attr("width", MARKER_R * 2)
        .attr("height", MARKER_R * 2)
        .attr("preserveAspectRatio", "xMidYMid slice")
        .attr("clip-path", `url(#${id})`);
    } else {
      g.append("circle").attr("class", "badge-bg crest").attr("r", MARKER_R);
      g.append("text").attr("class", "initials").attr("dy", "0.36em").text(initials(d.community.name));
    }
  });
  badge
    .append("text")
    .attr("class", "badge-label")
    .attr("y", MARKER_R + 26)
    .text((d) => d.community.shortName ?? d.community.name);
}

// Spread markers that sit on top of each other, keeping a leader line to
// their real location.
function layoutMarkers() {
  if (!current) return;
  const nodes = current.nodes;
  nodes.forEach((d, i) => {
    [d.ax, d.ay] = lastTransform.apply(d.anchor);
    // A tiny deterministic nudge so markers at the same spot fan out the same way every time.
    d.x = d.ax + Math.cos(i * 2.4) * 0.5;
    d.y = d.ay + Math.sin(i * 2.4) * 0.5;
  });
  d3.forceSimulation(nodes)
    .force("x", d3.forceX((d) => d.ax).strength(0.3))
    .force("y", d3.forceY((d) => d.ay).strength(0.3))
    .force("collide", d3.forceCollide(MARKER_R + 10))
    .stop()
    .tick(80);

  const groups = markerLayer.selectAll("g.marker");
  groups.select(".anchor").attr("cx", (d) => d.ax).attr("cy", (d) => d.ay);
  groups
    .select(".leader")
    .attr("x1", (d) => d.ax)
    .attr("y1", (d) => d.ay)
    .attr("x2", (d) => d.x)
    .attr("y2", (d) => d.y);
  groups.select(".badge").attr("transform", (d) => `translate(${d.x},${d.y})`);
  if (!card.hidden && cardNode) positionCard(cardNode);
}

function renderList(list) {
  listEl.replaceChildren();
  emptyEl.hidden = list.length > 0;
  list.forEach((community) => {
    const li = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.append(logoElement(community, "list-logo"));
    const text = document.createElement("span");
    const name = document.createElement("strong");
    name.textContent = community.name;
    text.append(name);
    if (community.region) {
      const region = document.createElement("small");
      region.textContent = community.region;
      text.append(region);
    }
    button.append(text);
    button.addEventListener("click", () => {
      const node = current.nodes.find((d) => d.community === community);
      openCard(node ?? { community });
    });
    li.append(button);
    listEl.append(li);
  });
}

/* ---------------------------------------------------------- community card */

function openCard(node) {
  const c = node.community;
  card.replaceChildren();

  const close = document.createElement("button");
  close.type = "button";
  close.className = "close";
  close.setAttribute("aria-label", "Close");
  close.textContent = "×";
  close.addEventListener("click", closeCard);

  const head = document.createElement("div");
  head.className = "card-head";
  const heading = document.createElement("div");
  const h = document.createElement("h4");
  h.id = "community-card-title";
  h.textContent = c.name;
  heading.append(h);
  if (c.region) {
    const p = document.createElement("p");
    p.className = "region";
    p.textContent = c.region;
    heading.append(p);
  }
  // The logo doubles as a button to the community's main link.
  const mainLink = (c.links ?? []).map((link) => safeUrl(link, linkInfo(link.type))).find(Boolean);
  const logo = logoElement(c, "card-logo");
  if (mainLink) {
    const a = document.createElement("a");
    a.className = "card-logo-link";
    a.href = mainLink;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.setAttribute("aria-label", `Open ${c.name}`);
    a.append(logo);
    head.append(a, heading);
  } else {
    head.append(logo, heading);
  }
  card.append(close, head);

  if (c.description) {
    const p = document.createElement("p");
    p.className = "desc";
    p.textContent = c.description;
    card.append(p);
  }

  const links = c.links ?? [];
  if (links.length) {
    const ul = document.createElement("ul");
    ul.className = "links";
    links.forEach((link) => ul.append(linkItem(link)));
    card.append(ul);
  } else {
    const p = document.createElement("p");
    p.className = "desc";
    p.textContent = "No contact details added yet.";
    card.append(p);
  }

  card.setAttribute("aria-labelledby", h.id);
  card.hidden = false;
  cardNode = node.anchor ? node : null;
  markerLayer.selectAll("g.marker").classed("active", (d) => d === node);
  positionCard(cardNode);
  close.focus();
}

function positionCard(node) {
  const wrap = mapWrap.getBoundingClientRect();
  const cardBox = card.getBoundingClientRect();
  if (!node) {
    card.style.left = `${(wrap.width - cardBox.width) / 2}px`;
    card.style.top = `${Math.max(8, (wrap.height - cardBox.height) / 2)}px`;
    return;
  }
  const sx = wrap.width / CW;
  const sy = wrap.height / CH;
  const mx = node.x * sx;
  const my = node.y * sy;
  const gap = (MARKER_R + 12) * sy;
  let top = my - gap - cardBox.height;
  if (top < 8) top = my + gap + 14;
  top = Math.min(top, wrap.height - cardBox.height - 8);
  const left = Math.min(Math.max(mx - cardBox.width / 2, 8), wrap.width - cardBox.width - 8);
  card.style.left = `${left}px`;
  card.style.top = `${Math.max(8, top)}px`;
}

function closeCard() {
  if (card.hidden) return;
  card.hidden = true;
  cardNode = null;
  markerLayer.selectAll("g.marker").classed("active", false);
}

function linkItem(link) {
  const info = linkInfo(link.type);
  const li = document.createElement("li");
  const url = safeUrl(link, info);
  const row = document.createElement(url ? "a" : "div");
  row.className = "link";
  row.style.setProperty("--brand", info.color);
  if (url) {
    row.href = url;
    row.target = "_blank";
    row.rel = "noopener noreferrer";
  }

  const icon = document.createElement("span");
  icon.className = "icon";
  icon.style.setProperty("--icon", `url("${info.icon}")`);
  icon.setAttribute("aria-hidden", "true");

  const text = document.createElement("span");
  text.className = "link-text";
  const kind = document.createElement("strong");
  kind.textContent = link.title ?? info.label;
  const detail = document.createElement("small");
  detail.textContent = link.label ?? link.url ?? "";
  text.append(kind, detail);
  row.append(icon, text);
  li.append(row);

  // Names without a link (e.g. "message Jan Kowalski on Messenger") get a copy button.
  if (!url && link.label) {
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "copy";
    copy.textContent = "Copy";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(link.label);
        copy.textContent = "Copied";
      } catch {
        copy.textContent = "Copy failed";
      }
      setTimeout(() => (copy.textContent = "Copy"), 1500);
    });
    row.append(copy);
  }
  return li;
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter((w) => /^[\p{L}\p{N}]/u.test(w) && !/^(of|the|and|de|la|le|der|die|das|i|w)$/i.test(w))
    .slice(0, 3)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function logoElement(community, className) {
  const el = document.createElement("span");
  el.className = `logo ${className}`;
  el.setAttribute("aria-hidden", "true");
  if (community.logo) {
    const img = document.createElement("img");
    img.src = community.logo;
    img.alt = "";
    el.append(img);
  } else {
    el.textContent = initials(community.name);
  }
  return el;
}

/* ----------------------------------------------------------- dialog wiring */

dialog.addEventListener("click", (event) => {
  if (event.target === dialog) dialog.close();
  if (event.target.closest("[data-close]")) dialog.close();
});

countrySvg.on("click", (event) => {
  if (event.target.closest(".badge")) return;
  closeCard();
});

dialog.addEventListener("cancel", (event) => {
  if (join.isPlanting()) {
    event.preventDefault();
    join.stop();
  } else if (!card.hidden) {
    event.preventDefault();
    closeCard();
  }
});

dialog.addEventListener("close", () => {
  closeCard();
  join.reset();
  current = null;
  history.replaceState(null, "", location.pathname + location.search);
});

function openFromHash() {
  const name = decodeURIComponent(location.hash.slice(1));
  const feature = name && byName.get(normalize(name));
  if (feature) openCountry(feature);
}

window.addEventListener("hashchange", openFromHash);
openFromHash();
