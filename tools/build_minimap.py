"""Builds the hit map for one country's ornate minimap.

    python build_minimap.py ../data/country-maps/sweden.json [--cells]

How each part of the minimap is identified:

- The featured country, by its painted gold fill (exact, whatever the pen
  lines do), with the trees, mountains and lakes inside it filled in. By
  default every solid gold area counts, islands included; "highlight": {"at":
  [[x, y], ...]} limits it to the pieces around those points.
- Neighbouring countries: the regions the pen lines enclose. Real borders are
  fitted onto the gold shape (Mercator, scaled to match it) and each sizeable
  drawn region goes to the real country covering most of it.
- "regions": [x, y, "Country"] names a region by hand, overriding the guess
  ("null" country makes it sea). Regions too small to name (inside drawn
  mountains, forests) join whichever country surrounds them.
- "water": [x, y] points inside drawn seas (never given to a country).
- "decorations": outlines of artwork that isn't geography. Defaults to the
  standard layout (frame, title, crest, dragons, compass, globe) scaled to
  the image ("extra_decorations" adds to it, "skip_decorations" drops parts). Never clickable, and they
  close off the regions they touch.
- "landmarks": [lon, lat, x, y] for placing community markers; defaults to
  points from the fitted real borders.
- "areas": [{"country": ..., "outline": [[x, y], ...]}] paints the land inside a
  traced outline, for borders the artwork doesn't draw.
- "foreign_gold": false keeps every gold piece for the featured country (by
  default, gold pieces over a neighbour's real territory go to it).
- "split_gold": ["Country", ...] splits the gold along real borders where
  the artist painted a neighbour in without drawing the border.
- "fit": "largest" fits real borders to the main landmass only, for maps
  with insets drawn elsewhere (Alaska, Hawaii).

--cells also writes tools/.cache/minimap-<name>-cells.png with every drawn
region numbered and named, for finding points to fix.
Writes <name>-hitmap.png and <name>-hitmap.json next to the config.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from hitmap_lib import components, dilate

ROOT = Path(__file__).resolve().parent.parent
config_path = Path(sys.argv[1]).resolve()
cfg = json.loads(config_path.read_text(encoding="utf8"))
name = config_path.stem
featured = cfg["country"]

INK = cfg.get("ink", 100)
SEAL = cfg.get("seal", 2)
INK_REACH = 8       # px of pen line absorbed into the region beside it
SMALL_REGION = 2500 # unnamed regions below this size join their surroundings
GUESS_MIN = 600     # drawn regions at least this big get a country from real borders
BROWN_OUTLINE = cfg.get("brown_outline")  # if set, regions outlined mostly in brown ink are skipped as drawings

# The standard minimap layout, as fractions of the image (x0, y0, x1, y1).
TEMPLATE = {
    "frame top": (0, 0, 1, 0.035),
    "frame bottom": (0, 0.95, 1, 1),
    "frame left": (0, 0, 0.04, 1),
    "frame right": (0.96, 0, 1, 1),
    "title": (0.27, 0, 0.74, 0.10),
    "crest and name": (0.05, 0.08, 0.315, 0.44),
    "dragon top left": (0, 0, 0.16, 0.20),
    "dragon top right": (0.84, 0, 1, 0.19),
    "compass": (0.03, 0.44, 0.165, 0.76),
    "globe": (0.455, 0.88, 0.545, 1),
    "corner bottom left": (0, 0.85, 0.12, 1),
    "corner bottom right": (0.88, 0.85, 1, 1),
}

# Maps recoloured green by recolour_green.py are detected from their gold copy.
gold_copy = ROOT / "assets/country-maps/gold" / Path(cfg["image"]).name
art = Image.open(gold_copy if gold_copy.exists() else ROOT / cfg["image"]).convert("RGB")
W, H = art.size
grey = np.asarray(art.convert("L"))

decorations = cfg.get("decorations") or {
    k: [[x0 * W, y0 * H], [x1 * W, y0 * H], [x1 * W, y1 * H], [x0 * W, y1 * H]] for k, (x0, y0, x1, y1) in TEMPLATE.items()
}
decorations = {k: v for k, v in decorations.items() if k not in cfg.get("skip_decorations", [])}
decorations = {**decorations, **cfg.get("extra_decorations", {})}
decor_img = Image.new("1", (W, H), 0)
for outline in decorations.values():
    ImageDraw.Draw(decor_img).polygon([tuple(p) for p in outline], fill=1)
decoration = np.asarray(decor_img)

ink = (grey < INK) & ~decoration
sealed = dilate(ink, SEAL) & ~decoration
# Decorations are walls: they close off the regions they touch.
regions, region_count = components(~(sealed | decoration))
sizes = np.bincount(regions[regions >= 0], minlength=region_count)

names = []
def label_for(country):
    if country not in names:
        names.append(country)
    return names.index(country) + 1

result = np.zeros((H, W), dtype=np.uint8)

for x, y in cfg.get("water", []):
    if regions[y, x] < 0:
        print(f"water point ({x}, {y}) is on a pen line, pick a point in open water")
water_ids = {int(regions[y, x]) for x, y in cfg.get("water", []) if regions[y, x] >= 0}

# ------------------------------------------------- the featured country, by colour

hl = cfg.get("highlight", {})
def box_mean(a, r):
    """Mean over a (2r+1)-square window: averages away noisy texture (the sea)."""
    c = np.pad(a.astype(float), r + 1, mode="edge").cumsum(0).cumsum(1)
    n = 2 * r + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n])[: a.shape[0], : a.shape[1]] / (n * n)


hsv = np.asarray(art.convert("HSV")).astype(int)
smooth = hl.get("smooth", 3)
h, s, v = (box_mean(hsv[..., i], smooth) for i in range(3))
lo, hi = hl.get("hue", [24, 40])
rgb_full = np.asarray(art).astype(int)
usable = (v >= 170) & (h >= lo) & (h <= hi) & ~dilate(decoration, 3)


def otsu(values):
    hist, edges = np.histogram(values, bins=128, range=(0, 256))
    w = np.cumsum(hist); m = np.cumsum(hist * edges[:-1])
    total, mean = w[-1], m[-1]
    between = (mean * w - m * total) ** 2 / np.maximum(w * (total - w), 1)
    return edges[np.argmax(between)]


# The gold is the most saturated bright colour on the map, the sea and other
# land are duller; where exactly the split falls differs per map.
min_sat = hl.get("min_saturation", float(np.clip(otsu(s[usable]), 130, 185)))
painted = usable & (s >= min_sat) & (v >= hl.get("min_value", 150))
seeds = hl.get("at", [])

# Join fragments (texture, rivers drawn across it) before judging pieces.
bridge = hl.get("bridge", 4)
painted = ~dilate(~dilate(painted, bridge), bridge)
parts, n_parts = components(painted)
py_, px_ = np.nonzero(parts >= 0)
pid = parts[py_, px_]
part_size = np.bincount(pid, minlength=n_parts)
mins_x = np.full(n_parts, W); maxs_x = np.full(n_parts, -1)
mins_y = np.full(n_parts, H); maxs_y = np.full(n_parts, -1)
np.minimum.at(mins_x, pid, px_); np.maximum.at(maxs_x, pid, px_)
np.minimum.at(mins_y, pid, py_); np.maximum.at(maxs_y, pid, py_)
bw = maxs_x - mins_x + 1; bh = maxs_y - mins_y + 1
island = (part_size >= hl.get("min_island", 120)) & (part_size >= 0.3 * bw * bh)
keep = (part_size >= hl.get("min_piece", 1500)) | island
# Drawn land has a pen outline; gold-tinted patches of sea texture don't.
for p_id in np.flatnonzero(keep):
    if part_size[p_id] > 60000:
        continue  # the mainland
    y0, x0 = max(mins_y[p_id] - 6, 0), max(mins_x[p_id] - 6, 0)
    y1, x1 = min(maxs_y[p_id] + 7, H), min(maxs_x[p_id] + 7, W)
    piece = parts[y0:y1, x0:x1] == p_id
    ring = dilate(piece, 5) & ~piece
    rgb_box = rgb_full[y0:y1, x0:x1]
    black = (grey[y0:y1, x0:x1] < 70) & (rgb_box[..., 0] - rgb_box[..., 2] < 40)  # coasts are black, ships and clouds brown
    if black[ring].mean() < hl.get("min_outline", 0.10):
        keep[p_id] = False
for x, y in seeds:
    if parts[y, x] >= 0:
        keep[parts[y, x]] = True
painted = (parts >= 0) & keep[np.maximum(parts, 0)]
parts, _ = components(painted)
if seeds:
    highlight = np.isin(parts, [parts[y, x] for x, y in seeds if parts[y, x] >= 0])
else:
    highlight = parts >= 0
# Fill what's drawn inside it (trees, mountains, small lakes); not the sea
# that islands enclose (Danish straits, the Aegean).
outside, n_out = components(~highlight)
hole_size = np.bincount(outside[outside >= 0], minlength=n_out)
small_hole = hole_size <= hl.get("max_hole", 2500)
border_ids = list(set(np.unique(np.concatenate([outside[0], outside[-1], outside[:, 0], outside[:, -1]]))) - {-1})
small_hole[border_ids] = False
highlight |= (outside >= 0) & small_hole[np.maximum(outside, 0)]
big_holes = (outside >= 0) & ~small_hole[np.maximum(outside, 0)] & ~np.isin(outside, border_ids)
gold_core = highlight.copy()
highlight = dilate(highlight, 2) & ~decoration  # take in its own outline
result[highlight] = label_for(featured)

# ----------------------------------------- neighbours: fit real borders onto the gold

countries = json.loads((ROOT / "tools/.cache/projected.json").read_text(encoding="utf8"))


def mercator(lon, lat):
    lat = np.clip(lat, -85, 85)
    return np.radians(lon), -np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))


def ring_area(xs, ys):
    return abs(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1))) / 2


def moments(mask):
    ys, xs = np.nonzero(mask)
    return xs.mean(), ys.mean(), xs.std(), ys.std()


home = next(c for c in countries if c["name"] == featured)
rings = [np.array(p[0], dtype=float) for p in home["lonlat"]]
main = max(rings, key=lambda r: ring_area(*mercator(r[:, 0], r[:, 1])))
gold_main = components(~dilate(~dilate(gold_core, 12), 12))[0]  # join pieces split by drawn rivers
biggest = np.bincount(gold_main[gold_main >= 0]).argmax()
if cfg.get("fit") == "largest":
    # Insets drawn apart (Alaska, Hawaii): fit the main landmass only.
    fit_rings = [main]
    fit_gold = gold_core & (gold_main == biggest)
else:
    # The whole country, minus far-flung territories.
    mx, my = mercator(main[:, 0], main[:, 1])
    reach = 3 * max(np.std(mx), np.std(my))
    fit_rings = [r for r in rings if np.hypot(*(np.array(mercator(r[:, 0].mean(), r[:, 1].mean())) - [mx.mean(), my.mean()])) < reach]
    gy, gx = np.nonzero(gold_main == biggest)
    gold_reach = 3 * max(gx.std(), gy.std())
    yy, xx = np.nonzero(gold_core)
    near = np.hypot(xx - gx.mean(), yy - gy.mean()) < gold_reach
    fit_gold = np.zeros_like(gold_core)
    fit_gold[yy[near], xx[near]] = True

# Real shape rasterised in Mercator, then matched to the gold by position and spread.
merc = [np.stack(mercator(r[:, 0], r[:, 1]), axis=1) for r in fit_rings]
allm = np.concatenate(merc)
grid = 900
x_min, y_min = allm.min(axis=0)
span = np.ptp(allm, axis=0).max()
canvas = Image.new("1", (grid, grid), 0)
for m in merc:
    ImageDraw.Draw(canvas).polygon([tuple(p) for p in (m - [x_min, y_min]) / span * (grid - 1)], fill=1)
rcx, rcy, rsx, rsy = moments(np.asarray(canvas))
k = span / (grid - 1)
rcx, rcy, rsx, rsy = rcx * k + x_min, rcy * k + y_min, rsx * k, rsy * k
gcx, gcy, gsx, gsy = moments(fit_gold)
sx, sy = gsx / rsx, gsy / rsy


def to_image(lon, lat):
    x, y = mercator(np.asarray(lon, float), np.asarray(lat, float))
    return (x - rcx) * sx + gcx, (y - rcy) * sy + gcy


geo_img = Image.new("L", (W, H), 0)
draw = ImageDraw.Draw(geo_img)
polys = []
for i, c in enumerate(countries):
    for poly in c["lonlat"]:
        outer = np.array(poly[0], dtype=float)
        x, y = to_image(outer[:, 0], outer[:, 1])
        if x.max() < -W or x.min() > 2 * W or y.max() < -H or y.min() > 2 * H:
            continue
        polys.append((ring_area(x, y), i, list(zip(x, y))))
for _, i, pts in sorted(polys, key=lambda t: -t[0]):
    draw.polygon(pts, fill=(i % 255) + 1)
geo = np.asarray(geo_img)
geo_name = {(i % 255) + 1: c["name"] for i, c in enumerate(countries)}

# Larger holes in the gold (mountain ranges, forests) are filled when the real
# country covers them; sea enclosed by islands isn't.
home_label = [k for k, n in geo_name.items() if n == featured]
hole_ids, n_holes = components(big_holes)
for hid in range(n_holes):
    member = hole_ids == hid
    if np.isin(geo[member], home_label).mean() > 0.5 and ((grey[member] < 60).mean() > 0.04 or member.sum() < 20000):
        highlight |= dilate(member, 2) & ~decoration
result[highlight] = label_for(featured)

# Gold pieces over another country's real territory (Corsica on the Italy map,
# Cyprus on Turkey's) belong to that country.
gold_pieces, n_gold = components(highlight)
for gid in range(n_gold if cfg.get("foreign_gold", True) else 0):
    member = gold_pieces == gid
    under = geo[member]
    under = under[under > 0]
    if not len(under):
        continue
    top = np.bincount(under).argmax()
    if geo_name.get(int(top)) != featured and not np.isin(under, home_label).mean() > 0.25 and (under == top).mean() > 0.5:
        highlight &= ~member
        result[member] = label_for(geo_name[int(top)])

# "split_gold": the artist painted a neighbour in with the featured country
# and drew no border (Northern Ireland): split the gold along the real border.
for country in cfg.get("split_gold", []):
    labels = [k for k, n in geo_name.items() if n == country]
    member = highlight & np.isin(geo, labels)
    highlight &= ~member
    result[member] = label_for(country)

# "areas": hand-traced outlines, for borders the artwork doesn't draw. Only
# land inside them changes, never sea.
area_masks = []
for area_def in cfg.get("areas", []):
    mask_img = Image.new("1", (W, H), 0)
    ImageDraw.Draw(mask_img).polygon([tuple(p) for p in area_def["outline"]], fill=1)
    inside = np.asarray(mask_img)
    if area_def.get("mode") == "all":
        member = inside & ~decoration & ~(highlight if area_def["country"] != featured else False)
    elif area_def.get("mode") == "land":
        # Everything drawn inside except open sea (the largest regions).
        member = inside & ~np.isin(regions, list(np.flatnonzero(sizes > 100000)) + list(water_ids))
    else:
        member = inside & (highlight | (result > 0))
    highlight &= ~member
    result[member] = label_for(area_def["country"])
    area_masks.append((member, label_for(area_def["country"])))

# Hand-named regions first, then guesses for the rest.
named = {}
for x, y, country in cfg.get("regions", []):
    r = int(regions[y, x])
    if r < 0:
        print(f"({x}, {y}) for {country} is on a pen line, pick a point inside the region")
        continue
    if named.get(r, country) != country:
        print(f"({x}, {y}) for {country} is in the same region as {named[r]}: a pen line has a gap")
    named[r] = country
for r, country in named.items():
    # A hand pin wins over the gold too (the artist may paint a neighbour in).
    member = dilate(regions == r, SEAL + 2) & ~decoration if country != featured else regions == r
    if country != featured:
        highlight &= ~member
    result[member] = label_for(country) if country else 0

# Clouds, ships and waves are drawn in brown; borders and coasts in black or navy.
rgb_arr = np.asarray(art).astype(int)
brown_ink = ink & (rgb_arr[..., 0] - rgb_arr[..., 2] > 35) & (grey > 35)


def outlined_in_brown(member_box, y0, x0):
    ring = dilate(member_box, SEAL + 2) & ~member_box & ink[y0:y0 + member_box.shape[0], x0:x0 + member_box.shape[1]]
    return ring.any() and brown_ink[y0:y0 + member_box.shape[0], x0:x0 + member_box.shape[1]][ring].mean() > BROWN_OUTLINE


guessed = []
flat_regions = regions.ravel()
ry, rx = np.nonzero(regions >= 0)
rid = regions[ry, rx]
rbox = np.full((region_count, 4), [H, W, -1, -1])
np.minimum.at(rbox[:, 0], rid, ry); np.minimum.at(rbox[:, 1], rid, rx)
np.maximum.at(rbox[:, 2], rid, ry); np.maximum.at(rbox[:, 3], rid, rx)
order = np.argsort(flat_regions, kind="stable")
starts = np.searchsorted(flat_regions[order], np.arange(region_count + 1))
flat_geo = geo.ravel()
flat_hl = highlight.ravel()
for r in np.flatnonzero(sizes >= GUESS_MIN):
    if r in named or r in water_ids:
        continue
    members = order[starts[r] : starts[r + 1]]
    if flat_hl[members].mean() > 0.3:
        continue
    y0, x0, y1, x1 = rbox[r, 0], rbox[r, 1], rbox[r, 2] + 1, rbox[r, 3] + 1
    if BROWN_OUTLINE is not None and outlined_in_brown(regions[y0:y1, x0:x1] == r, y0, x0):
        continue
    votes = np.bincount(flat_geo[members], minlength=256)
    land = votes.copy()
    land[0] = 0
    if featured in geo_name.values():
        land[[k for k, n in geo_name.items() if n == featured]] = 0
    if land.sum() < 0.5 * len(members):
        continue  # mostly sea in real life
    country = geo_name[int(land.argmax())]
    result.ravel()[members[~flat_hl[members]]] = label_for(country)
    guessed.append(country)

# ------------------------------------------------------------ fill in the rest

water = np.isin(regions, list(water_ids))
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
small = [r for r in np.flatnonzero(sizes < SMALL_REGION) if r not in water_ids and r not in named]
land_real = geo > 0
for _ in range(4):
    # Judge each small region by what surrounds it once the pen lines are
    # counted, without letting labels creep along the sea's wave strokes.
    around_view = grow_into_ink(result, pad + 2)
    for r in small:
        y0, x0 = max(box[r, 0] - pad, 0), max(box[r, 1] - pad, 0)
        y1, x1 = min(box[r, 2] + pad + 1, H), min(box[r, 3] + pad + 1, W)
        member = regions[y0:y1, x0:x1] == r
        local = result[y0:y1, x0:x1]
        if local[member].any() or land_real[y0:y1, x0:x1][member].mean() < 0.5:
            continue  # already named, or sea in real life (a wave cell)
        around = around_view[y0:y1, x0:x1][dilate(member, pad) & ~member]
        if len(around) and (around > 0).mean() > 0.85:
            counts = np.bincount(around[around > 0])
            if counts.max() > 0.9 * counts.sum():
                local[member] = counts.argmax()
result = grow_into_ink(result, INK_REACH)
result[highlight] = label_for(featured)
for member, label in area_masks:  # traced areas win over every guess
    result[member] = label
result[decoration] = 0

# ------------------------------------------------------------------- output

Image.fromarray(result, mode="L").save(config_path.with_name(f"{name}-hitmap.png"), optimize=True)

label_points = {}
for i, country in enumerate(names):
    ys, xs = np.nonzero(result == i + 1)
    if len(xs):
        k = np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2)
        label_points[country] = [int(xs[k]), int(ys[k])]

landmarks = cfg.get("landmarks")
if not landmarks:
    lon0, lat0 = np.concatenate(fit_rings)[:, 0], np.concatenate(fit_rings)[:, 1]
    landmarks = []
    for fx in (0, 0.5, 1):
        for fy in (0, 0.5, 1):
            lon = lon0.min() + fx * np.ptp(lon0)
            lat = lat0.min() + fy * np.ptp(lat0)
            x, y = to_image(lon, lat)
            landmarks.append([round(lon, 3), round(lat, 3), round(float(x), 1), round(float(y), 1)])

config_path.with_name(f"{name}-hitmap.json").write_text(
    json.dumps({"width": W, "height": H, "names": names, "labelPoints": label_points, "landmarks": landmarks}, ensure_ascii=False),
    encoding="utf8",
)
print(f"{name} (gold saturation >= {min_sat:.0f}): {region_count} drawn regions; on the map: {', '.join(sorted(label_points))}")

if "--unnamed" in sys.argv:
    # Big, compact drawn regions still unnamed: likely land that needs a pin.
    sat = box_mean(hsv[..., 1], 1)
    report_rows = []
    for r in np.flatnonzero(sizes >= 2500):
        if r in water_ids:
            continue
        members = order[starts[r] : starts[r + 1]]
        if (result.ravel()[members] > 0).mean() > 0.2:
            continue
        y0, x0, y1, x1 = rbox[r]
        fill_ratio = len(members) / ((y1 - y0 + 1) * (x1 - x0 + 1))
        if fill_ratio < 0.3:
            continue
        ys, xs = np.divmod(members, W)
        k = np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2)
        under = flat_geo[members]
        guess = geo_name.get(int(np.bincount(under[under > 0]).argmax())) if (under > 0).any() else "-"
        report_rows.append((len(members), int(xs[k]), int(ys[k]), round(fill_ratio, 2), guess))
    for row in sorted(report_rows, reverse=True):
        print("  unnamed", row)

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
