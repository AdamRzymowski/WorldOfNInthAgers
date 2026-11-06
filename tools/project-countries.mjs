// Projects every country onto the artwork's pixel grid (same warp as the
// site uses) so build_hitmap.py can rasterise them.
import fs from "fs";
import * as topojson from "topojson-client";
import { toImage, wrapLongitude, spansDateline } from "../js/calibration.js";

const root = new URL("..", import.meta.url);
const topology = JSON.parse(fs.readFileSync(new URL("data/countries-50m.json", root)));
const countries = topojson
  .feature(topology, topology.objects.countries)
  .features.filter((f) => f.properties.name !== "Antarctica");

const out = countries.map((f) => {
  const wraps = spansDateline(f);
  const polygons = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
  return {
    name: f.properties.name,
    lonlat: polygons,
    polygons: polygons.map((rings) =>
      rings.map((ring) =>
        ring.map(([lon, lat]) => toImage(wrapLongitude(lon, f.properties.name, wraps), lat).map((v) => +v.toFixed(1)))
      )
    ),
  };
});

fs.mkdirSync(new URL("tools/.cache/", root), { recursive: true });
fs.writeFileSync(new URL("tools/.cache/projected.json", root), JSON.stringify(out));
console.log(`projected ${out.length} countries`);
