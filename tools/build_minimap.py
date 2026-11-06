"""Builds the hit map for one country's ornate minimap.

    python build_minimap.py ../data/country-maps/sweden.json [--cells]

Minimaps are drawn too freely to bend real borders onto, so every drawn
region is named by hand in the config:

- "highlight": the featured country, found by its painted colour (the gold
  fill) around the "at" point(s), with the trees, mountains and lakes inside
  it filled in. Give one point per separate piece (islands).
- "regions": [x, y, "Country"] names the region the pen lines enclose around
  that pixel. Regions too small to name (inside drawn mountains, forests)
  join whichever country surrounds them.
- "water": [x, y] points inside drawn seas.
- "decorations": outlines of artwork that isn't geography (crest, compass,
  ships...); never clickable, and they close off the regions they touch.

--cells also writes tools/.cache/minimap-<name>-cells.png with every drawn
region numbered, for finding the points to name.
Writes <hitmap>.png and <hitmap>.json next to the config.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from hitmap_lib import components, dilate

ROOT = Path(__file__).resolve().parent.parent
config_path = Path(sys.argv[1]).resolve()
cfg = json.loads(config_path.read_text(encoding="utf8"))
name = config_path.stem

INK = cfg.get("ink", 100)
SEAL = cfg.get("seal", 1)
INK_REACH = 12      # px of pen line absorbed into the region beside it
SMALL_REGION = 2500 # unnamed regions below this size join their surroundings

art = Image.open(ROOT / cfg["image"]).convert("RGB")
W, H = art.size
grey = np.asarray(art.convert("L"))

decor_img = Image.new("1", (W, H), 0)
for outline in cfg.get("decorations", {}).values():
    ImageDraw.Draw(decor_img).polygon([tuple(p) for p in outline], fill=1)
decoration = np.asarray(decor_img)

ink = (grey < INK) & ~decoration
sealed = dilate(ink, SEAL) & ~decoration
# Decorations are walls: they close off the regions they touch.
regions, region_count = components(~(sealed | decoration))

names = sorted({c for _, _, c in cfg.get("regions", [])} | ({cfg["highlight"]["country"]} if "highlight" in cfg else set()))
label_of = {n: i + 1 for i, n in enumerate(names)}
result = np.zeros((H, W), dtype=np.uint8)

for x, y in cfg.get("water", []):
    if regions[y, x] < 0:
        print(f"water point ({x}, {y}) is on a pen line, pick a point in open water")
water_ids = {int(regions[y, x]) for x, y in cfg.get("water", []) if regions[y, x] >= 0}
water = np.isin(regions, list(water_ids))

named = {}
for x, y, country in cfg.get("regions", []):
    r = int(regions[y, x])
    if r < 0:
        print(f"({x}, {y}) for {country} is on a pen line, pick a point inside the region")
        continue
    if named.get(r, country) != country:
        print(f"({x}, {y}) for {country} is in the same region as {named[r]}: a pen line has a gap")
    if r in water_ids:
        print(f"({x}, {y}) for {country} is in a region marked as water")
    named[r] = country
    result[regions == r] = label_of[country]

# The featured country, by its painted colour: exact, whatever the pen lines do.
highlight = np.zeros((H, W), dtype=bool)
if "highlight" in cfg:
    hl = cfg["highlight"]
    hsv = np.asarray(art.convert("HSV")).astype(int)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    lo, hi = hl.get("hue", [18, 42])
    painted = (h >= lo) & (h <= hi) & (s >= hl.get("min_saturation", 150)) & (v >= hl.get("min_value", 150)) & ~decoration
    seeds = hl["at"] if isinstance(hl["at"][0], list) else [hl["at"]]
    # Keep only solid painted areas (not stray gold-ish texture elsewhere), then
    # close small breaks between them (rivers drawn across it) without growing outwards.
    parts, n_parts = components(painted)
    part_size = np.bincount(parts[parts >= 0], minlength=n_parts)
    keep = part_size >= hl.get("min_piece", 1500)
    keep[[parts[y, x] for x, y in seeds if parts[y, x] >= 0]] = True
    painted = (parts >= 0) & keep[np.maximum(parts, 0)]
    bridge = hl.get("bridge", 4)
    painted = ~dilate(~dilate(painted, bridge), bridge)
    parts, _ = components(painted)
    highlight = np.isin(parts, [parts[y, x] for x, y in seeds if parts[y, x] >= 0])
    # Fill what's drawn inside it (trees, mountains, lakes).
    outside, _ = components(~highlight)
    border_ids = set(np.unique(np.concatenate([outside[0], outside[-1], outside[:, 0], outside[:, -1]]))) - {-1}
    highlight |= (outside >= 0) & ~np.isin(outside, list(border_ids))
    highlight = dilate(highlight, 2) & ~decoration  # take in its own outline
    result[highlight] = label_of[hl["country"]]

# Small unnamed regions (inside drawn forests and mountains) join the country
# around them.
sizes = np.bincount(regions[regions >= 0], minlength=region_count)
ys, xs = np.nonzero(regions >= 0)
ids = regions[ys, xs]
box = np.full((region_count, 4), [H, W, -1, -1])
np.minimum.at(box[:, 0], ids, ys)
np.minimum.at(box[:, 1], ids, xs)
np.maximum.at(box[:, 2], ids, ys)
np.maximum.at(box[:, 3], ids, xs)
fill = sealed & ~water


def grow_into_ink(result, steps):
    """Pen lines belong to the land beside them."""
    for _ in range(steps):
        grow = result.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            shifted = np.roll(result, (dy, dx), axis=(0, 1))
            take = (grow == 0) & fill & (shifted != 0)
            grow[take] = shifted[take]
        result = grow
    return result


pad = SEAL + 4
small = [r for r in np.flatnonzero(sizes < SMALL_REGION) if r not in water_ids]
for _ in range(4):
    result = grow_into_ink(result, INK_REACH)
    for r in small:
        y0, x0 = max(box[r, 0] - pad, 0), max(box[r, 1] - pad, 0)
        y1, x1 = min(box[r, 2] + pad + 1, H), min(box[r, 3] + pad + 1, W)
        member = regions[y0:y1, x0:x1] == r
        local = result[y0:y1, x0:x1]
        if local[member].any():
            continue
        # Only when one country clearly surrounds it (not a wave cell by the coast).
        around = local[dilate(member, pad) & ~member]
        if len(around) and (around > 0).mean() > 0.85:
            counts = np.bincount(around[around > 0])
            if counts.max() > 0.9 * counts.sum():
                local[member] = counts.argmax()
result = grow_into_ink(result, INK_REACH)
if "highlight" in cfg:
    result[highlight] = label_of[cfg["highlight"]["country"]]

result[decoration] = 0
out_png = config_path.with_name(f"{name}-hitmap.png")
Image.fromarray(result, mode="L").save(out_png, optimize=True)

label_points = {}
for country, v in label_of.items():
    ys, xs = np.nonzero(result == v)
    if len(xs):
        k = np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2)
        label_points[country] = [int(xs[k]), int(ys[k])]
config_path.with_name(f"{name}-hitmap.json").write_text(
    json.dumps({"width": W, "height": H, "names": names, "labelPoints": label_points}, ensure_ascii=False),
    encoding="utf8",
)
print(f"{region_count} drawn regions; {len(label_points)} countries on the {name} minimap")

if "--cells" in sys.argv:
    big = np.flatnonzero(sizes >= 300)
    rng = np.random.default_rng(3)
    palette = rng.integers(70, 255, (region_count, 3))
    rgb = np.asarray(art).astype(float) * 0.35
    shown = np.isin(regions, big)
    rgb[shown] = rgb[shown] + palette[regions[shown]] * 0.65
    img = Image.fromarray(rgb.astype(np.uint8))
    d = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=16)
    for r in big:
        ys, xs = np.nonzero(regions == r)
        k = np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2)
        tag = names[result[ys[k], xs[k]] - 1] if result[ys[k], xs[k]] else ""
        d.text((xs[k], ys[k]), f"{xs[k]},{ys[k]} {tag}", fill=(0, 0, 0), font=font, anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255))
    out = ROOT / "tools/.cache" / f"minimap-{name}-cells.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out)
