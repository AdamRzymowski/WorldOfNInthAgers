"""Builds data/hitmap.png: which country each pixel of the artwork belongs to.

The artwork is hand-drawn, so neither its coastlines nor its borders follow
real geography exactly. To make hover and clicks match what you can see:

1. Find the regions the artwork encloses with ink (after sealing small gaps
   in the pen lines), which of them is the open ocean, and which ink lines
   are coastlines and which are borders.
2. Bend real geography onto the drawing. Start from the landmark warp in
   js/calibration.js; then, tile by tile, find the shift that best lays the
   real coasts and borders over the drawn ones; then pull every real line
   onto the nearest drawn line of the same kind (coarse to fine, smoothed so
   neighbours move together).
3. Give each drawn land region to the country that covers most of it. Where
   one drawn region holds two countries (the artist left a border out), split
   it along the real border. Inside the ocean region only real land counts.
4. Apply overrides.json for anything that still comes out wrong.

Run `npm run hitmap` (projects the countries with Node, then runs this).
Needs Python with Pillow and numpy. Check the result with review_hitmap.py.
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from hitmap_lib import components, dilate, disk_offsets, nearest_site

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "tools/.cache"

INK = 100            # pixels darker than this are pen lines
SEAL = 1             # pen-line gaps up to 2*SEAL+1 px are closed when finding regions
SEAL_WIDE = 3        # wider gaps closed when looking for islands whose outlines leak
LEAKY_LAND = 0.4     # ...which only count as islands with at least this share of real land under them
MIXED_SHARE = 0.25   # a runner-up country this big means the region holds two countries
MIN_KEEP = 0.2       # countries left with less than this share of their real area get it back
INK_REACH = 10       # how far (px) ink (borders, drawn trees and mountains) is absorbed into the land around it
OCEAN_LAND_REACH = 3 # in the open sea, real land only counts this close (px) to a drawn line or dot
SPILL_REACH = 14     # real land in the sea this close (px) to the same country's drawn land is dropped
LAKE_DIST = 8       # drawn regions over real sea count as water when this far (px, median) from real land
OCEAN_SEEDS = [(120, 520), (640, 470), (1200, 640), (1700, 400), (700, 800), (300, 700)]
# Seas the artwork encloses completely (so they aren't part of the ocean region).
WATER_SEEDS = {
    "Mediterranean": (905, 367),
    "Black Sea": (1011, 324),
    "Caspian Sea": (1097, 334),
    "Baltic Sea": (933, 224),
    "Hudson Bay": (442, 203),
    "Sea of Okhotsk": (1562, 259),
}
# Artwork that isn't geography (frame, title, dragons, compass, ships, sea
# creatures, scale bar): its ink is ignored. Outlines in image pixels.
DECORATIONS = {
    "frame left": [(0, 0), (46, 0), (46, 887), (0, 887)],
    "frame right": [(1730, 0), (1774, 0), (1774, 887), (1730, 887)],
    "frame top": [(0, 0), (1774, 0), (1774, 10), (0, 10)],
    "frame bottom": [(0, 852), (1774, 852), (1774, 887), (0, 887)],
    "dragon top left": [(0, 0), (265, 0), (265, 74), (196, 88), (190, 120), (84, 124), (72, 175), (46, 175), (46, 0)],
    "title scroll": [(480, 0), (1196, 0), (1196, 76), (480, 86)],
    "title ribbon": [(596, 94), (660, 86), (668, 76), (1180, 76), (1180, 116), (1135, 121), (1100, 128), (1000, 140), (892, 142), (888, 158), (868, 158), (862, 142), (700, 140), (664, 126), (596, 116)],
    "dragon top right": [(1605, 10), (1774, 10), (1774, 262), (1712, 262), (1705, 140), (1605, 136)],
    "compass": [(40, 636), (248, 636), (248, 840), (40, 840)],
    "neptune": [(214, 704), (376, 704), (376, 822), (214, 822)],
    "corner bottom left": [(0, 770), (130, 770), (262, 852), (0, 852)],
    "globe": [(804, 788), (936, 788), (936, 852), (804, 852)],
    "kraken": [(1208, 698), (1392, 698), (1392, 802), (1208, 802)],
    "scale bar": [(1408, 802), (1646, 802), (1646, 846), (1408, 846)],
    "corner bottom right": [(1690, 800), (1730, 760), (1730, 852), (1640, 852)],
    "ship north atlantic": [(626, 232), (698, 232), (698, 284), (626, 284)],
    "ship mid atlantic": [(586, 398), (654, 398), (654, 466), (586, 466)],
    "ship pacific west": [(82, 520), (178, 520), (178, 628), (82, 628)],
    "ship indian ocean": [(1080, 664), (1174, 664), (1174, 780), (1080, 780)],
    "ship pacific east": [(1556, 406), (1626, 406), (1626, 476), (1556, 476)],
    "cloud west atlantic": [(480, 348), (564, 348), (564, 382), (480, 382)],
    "cloud south atlantic": [(544, 736), (684, 736), (684, 780), (544, 780)],
    "ornament bottom left": [(540, 806), (806, 806), (806, 852), (540, 852)],
    "ornament bottom right": [(934, 806), (1210, 806), (1210, 852), (934, 852)],
    "cloud east siberian sea": [(1534, 94), (1612, 94), (1612, 126), (1534, 126)],
    "cloud pacific north": [(1604, 454), (1714, 454), (1714, 502), (1604, 502)],
    "cloud pacific south": [(1654, 498), (1736, 498), (1736, 542), (1654, 542)],
    "sea serpent": [(126, 436), (250, 436), (250, 484), (126, 484)],
}
# Decorations drawn over land (the title covers northern Greenland): they close
# off the regions they cut through instead of being ignored.
WALLS = {"title scroll", "title ribbon"}
BLOCK_ROUNDS = [(192, 48, 3), (128, 30, 2), (80, 18, 2), (48, 10, 1)]  # (tile px, max shift px, step px)
CHAMFER_CAP = 8      # distances beyond this count the same when scoring a tile's fit
SNAP_ROUNDS = [(10, 10), (8, 8), (6, 6), (5, 5), (4, 4)]  # (search radius px, smoothing px)


# ----------------------------------------------------------------- helpers

def gaussian_blur(a, sigma):
    """Gaussian blur via FFT, zero padding outside the image."""
    h, w = a.shape
    pad = int(3 * sigma)
    big = np.zeros((h + 2 * pad, w + 2 * pad))
    big[pad : pad + h, pad : pad + w] = a
    fy = np.fft.fftfreq(big.shape[0])[:, None]
    fx = np.fft.fftfreq(big.shape[1])[None, :]
    kernel = np.exp(-2 * (np.pi * sigma) ** 2 * (fy**2 + fx**2))
    out = np.real(np.fft.ifft2(np.fft.fft2(big) * kernel))
    return out[pad : pad + h, pad : pad + w]


def smooth_field(points, deltas, weights, sigma, shape):
    """Smooth displacement field from scattered (point, delta) pairs; ~0 where no data."""
    h, w = shape
    xi = np.clip(np.round(points[:, 0]).astype(int), 0, w - 1)
    yi = np.clip(np.round(points[:, 1]).astype(int), 0, h - 1)
    acc = np.zeros((3, h, w))
    np.add.at(acc[0], (yi, xi), deltas[:, 0] * weights)
    np.add.at(acc[1], (yi, xi), deltas[:, 1] * weights)
    np.add.at(acc[2], (yi, xi), weights)
    bx, by, bw = (gaussian_blur(c, sigma) for c in acc)
    prior = 0.5 / (2 * np.pi * sigma * sigma)  # half a sample's worth of "stay put"
    return bx / (bw + prior), by / (bw + prior)


def sample(field, pts):
    """Bilinear lookup of a (fx, fy) field at float points."""
    fx, fy = field
    h, w = fx.shape
    x = np.clip(pts[:, 0], 0, w - 1.001)
    y = np.clip(pts[:, 1], 0, h - 1.001)
    x0 = np.floor(x).astype(int)
    y0 = np.floor(y).astype(int)
    ax, ay = x - x0, y - y0

    def lerp(f):
        return (f[y0, x0] * (1 - ax) * (1 - ay) + f[y0, x0 + 1] * ax * (1 - ay)
                + f[y0 + 1, x0] * (1 - ax) * ay + f[y0 + 1, x0 + 1] * ax * ay)

    return np.stack([lerp(fx), lerp(fy)], axis=1)


# ------------------------------------------------------ 1. drawn regions

art = Image.open(ROOT / "assets/world-map.webp").convert("L")
W, H = art.size
decor_img = Image.new("1", (W, H), 0)
wall_img = Image.new("1", (W, H), 0)
for name, outline in DECORATIONS.items():
    ImageDraw.Draw(wall_img if name in WALLS else decor_img).polygon(outline, fill=1)
wall = np.asarray(wall_img)
decoration = np.asarray(decor_img) | wall
ink = (np.asarray(art) < INK) & ~decoration
sealed = dilate(ink, SEAL) & ~decoration
regions, region_count = components(~(sealed | wall))

ocean_ids = {int(regions[y, x]) for x, y in OCEAN_SEEDS if regions[y, x] >= 0}
ocean = np.isin(regions, list(ocean_ids))
for sea, (x, y) in WATER_SEEDS.items():
    if regions[y, x] < 0 or int(regions[y, x]) in ocean_ids:
        print(f"water seed for {sea} at ({x}, {y}) is not inside an enclosed drawn region")
water_ids = ocean_ids | {int(regions[y, x]) for x, y in WATER_SEEDS.values() if regions[y, x] >= 0}
water = np.isin(regions, list(water_ids))
sizes = np.bincount(regions[regions >= 0], minlength=region_count)
land_cell = (regions >= 0) & ~water & (sizes[np.maximum(regions, 0)] > 30)

# Drawn coastline: ink between a land region and the ocean. Drawn border:
# ink between two sizeable land regions (so not the inside of a drawn
# mountain or tree).
reach = SEAL + 2
coast_ink = sealed & dilate(water, reach) & dilate(land_cell, reach)

NONE = np.iinfo(np.int32).max
big_id = np.where(land_cell & (sizes[np.maximum(regions, 0)] > 150), regions, -1)
big_or_none = np.where(big_id >= 0, big_id, NONE)
hi, lo = big_id.copy(), big_or_none.copy()
for dy, dx in disk_offsets(reach):
    hi = np.maximum(hi, np.roll(big_id, (dy, dx), axis=(0, 1)))
    lo = np.minimum(lo, np.roll(big_or_none, (dy, dx), axis=(0, 1)))
border_ink = sealed & (hi >= 0) & (lo < hi) & ~coast_ink

# ------------------------------------------- 2. bend real geography onto it

countries = json.loads((CACHE / "projected.json").read_text(encoding="utf8"))
names = [c["name"] for c in countries]

# Flatten every ring into one vertex array so a single warp moves them all.
rings = []  # (country index, polygon index, ring index, start, end)
parts = []
offset = 0
for ci, c in enumerate(countries):
    for pi, polygon in enumerate(c["polygons"]):
        for ri, ring in enumerate(polygon):
            parts.append(np.array(ring, dtype=float))
            rings.append((ci, pi, ri, offset, offset + len(ring)))
            offset += len(ring)
verts = np.concatenate(parts)


def key(p):
    return (round(p[0], 1), round(p[1], 1))


# Coastline edges belong to one country; border edges are shared by two.
edge_count = {}
for _, _, _, s, e in rings:
    for i in range(s, e - 1):
        k = frozenset((key(verts[i]), key(verts[i + 1])))
        edge_count[k] = edge_count.get(k, 0) + 1

edge_a, edge_b, edge_kind = [], [], []  # kind 0 = coast, 1 = border
seen_border = set()
has_border = np.zeros(len(countries), dtype=bool)
for ci, _, _, s, e in rings:
    for i in range(s, e - 1):
        k = frozenset((key(verts[i]), key(verts[i + 1])))
        if edge_count[k] == 1:
            edge_a.append(i); edge_b.append(i + 1); edge_kind.append(0)
        else:
            has_border[ci] = True
            if k not in seen_border:
                seen_border.add(k)
                edge_a.append(i); edge_b.append(i + 1); edge_kind.append(1)
edge_a, edge_b, edge_kind = map(np.array, (edge_a, edge_b, edge_kind))

# Sample points along every edge (~2 px apart), as fixed blends of the edge's
# end vertices so they move with them.
lengths = np.linalg.norm(verts[edge_b] - verts[edge_a], axis=1)
steps = np.maximum(1, np.ceil(lengths / 2).astype(int))
sample_edge = np.repeat(np.arange(len(edge_a)), steps)
sample_t = np.concatenate([np.arange(n) / n for n in steps])[:, None]
sample_kind = edge_kind[sample_edge]
sample_w = np.where(sample_kind == 0, 1.0, 0.5)
coast = sample_kind == 0


def samples(v):
    a = v[edge_a[sample_edge]]
    b = v[edge_b[sample_edge]]
    return a + (b - a) * sample_t


def lookup(pts):
    xi = np.clip(np.round(pts[..., 0]).astype(int), 0, W - 1)
    yi = np.clip(np.round(pts[..., 1]).astype(int), 0, H - 1)
    return xi, yi


coast_sy, coast_sx, coast_d2 = nearest_site(coast_ink)
border_sy, border_sx, border_d2 = nearest_site(border_ink)
coast_dist, border_dist = np.sqrt(coast_d2), np.sqrt(border_d2)
base_verts = verts.copy()


def chamfer(pts, kinds, weights):
    """Weighted mean truncated distance from real lines to drawn lines of the same kind."""
    xi, yi = lookup(pts)
    d = np.where(kinds == 0, coast_dist[yi, xi], border_dist[yi, xi])
    return (np.minimum(d, CHAMFER_CAP) * weights).sum(axis=-1) / weights.sum(axis=-1)


def report(label):
    pts = samples(verts)
    xi, yi = lookup(pts)
    c = np.median(np.minimum(coast_dist[yi[coast], xi[coast]], 30))
    b = np.median(np.minimum(border_dist[yi[~coast], xi[~coast]], 30))
    print(f"{label:<28} median distance to drawn line: coasts {c:.2f}px, borders {b:.2f}px")


if "--reuse-warp" in sys.argv and (CACHE / "snapped.npy").exists():
    verts = np.load(CACHE / "snapped.npy")  # only overrides changed: skip the slow part
else:
    report("landmark warp")

    # Stage 1: for overlapping tiles, the shift that best lays the tile's real
    # coasts and borders over the drawn ones. Matching a whole tile's shape at
    # once can't be fooled by a single nearby island the way snapping can.
    for tile, search, step in BLOCK_ROUNDS:
        pts = samples(verts)
        centres, shifts, confidence = [], [], []
        half = tile // 2
        grid = np.arange(-search, search + 1, step)
        T = np.array([(dx, dy) for dy in grid for dx in grid], dtype=float)
        fine = np.array([(dx, dy) for dy in range(-step, step + 1) for dx in range(-step, step + 1)], dtype=float)
        for cy in range(0, H + half, half):
            for cx in range(0, W + half, half):
                sel = (np.abs(pts[:, 0] - cx) < half) & (np.abs(pts[:, 1] - cy) < half)
                if (sel & coast).sum() < 25 and sel.sum() < 60:
                    continue
                P, K, Wt = pts[sel], sample_kind[sel], sample_w[sel]
                if len(P) > 1200:
                    pick = np.linspace(0, len(P) - 1, 1200).astype(int)
                    P, K, Wt = P[pick], K[pick], Wt[pick]
                cost = chamfer(P[None] + T[:, None], K[None], Wt[None])
                cost += 0.004 * np.linalg.norm(T, axis=1)  # prefer small moves on ties
                cand = fine + T[np.argmin(cost)]
                fcost = chamfer(P[None] + cand[:, None], K[None], Wt[None])
                fit = max(0.0, 1 - fcost.min() / CHAMFER_CAP)
                centres.append((cx, cy))
                shifts.append(cand[np.argmin(fcost)])
                confidence.append(fit * fit * len(P))
        field = smooth_field(np.array(centres, float), np.array(shifts), np.array(confidence), tile * 0.45, (H, W))
        verts = verts + sample(field, verts)
        report(f"block match {tile}px")

    # Stage 2: pull each real line onto the nearest drawn line of the same kind.
    for radius, sigma in SNAP_ROUNDS:
        pts = samples(verts)
        xi, yi = lookup(pts)
        target = np.where(
            coast[:, None],
            np.stack([coast_sx[yi, xi], coast_sy[yi, xi]], axis=1),
            np.stack([border_sx[yi, xi], border_sy[yi, xi]], axis=1),
        ).astype(float)
        delta = target - pts
        dist = np.linalg.norm(delta, axis=1)
        keep = dist < radius
        weights = (sample_w * np.where(dist < radius / 2, 1.0, 1 - (dist - radius / 2) / (radius / 2)))[keep]

        # And the other way round: drawn coast pulls the nearest real coast to it,
        # so drawn features without a nearby real counterpart still get matched.
        raster = np.zeros((H, W), dtype=bool)
        raster[yi[coast], xi[coast]] = True
        owner = np.full((H, W), -1, dtype=np.int64)
        owner[yi[coast], xi[coast]] = np.flatnonzero(coast)
        ny, nx, nd = nearest_site(raster)
        cy, cx = np.nonzero(coast_ink)
        back_keep = np.sqrt(nd[cy, cx]) < radius
        src = owner[ny[cy, cx], nx[cy, cx]][back_keep]
        back_pts = pts[src]
        back_delta = np.stack([cx, cy], axis=1)[back_keep] - back_pts

        field = smooth_field(
            np.concatenate([pts[keep], back_pts]),
            np.concatenate([delta[keep], back_delta]),
            np.concatenate([weights, 0.5 * np.ones(len(src))]),
            sigma,
            (H, W),
        )
        verts = verts + sample(field, verts)
        report(f"snap r={radius} sigma={sigma}")


# ---------------------------------------------------- 3. assign regions

def ring_area(r):
    return abs(np.dot(r[:, 0], np.roll(r[:, 1], 1)) - np.dot(r[:, 1], np.roll(r[:, 0], 1))) / 2


area = np.zeros(len(countries))
for ci, pi, ri, s, e in rings:
    if ri == 0:
        area[ci] += ring_area(verts[s:e])
geo_img = Image.new("L", (W, H), 0)
draw = ImageDraw.Draw(geo_img)
by_country = {}
for ci, pi, ri, s, e in rings:
    by_country.setdefault(ci, []).append((pi, ri, s, e))
for ci in np.argsort(-area):  # large countries first so enclaves land on top
    for pi, ri, s, e in by_country[ci]:
        draw.polygon([tuple(p) for p in verts[s:e]], fill=0 if ri else int(ci) + 1)
geo = np.asarray(geo_img).copy()

overrides = json.loads((ROOT / "tools/overrides.json").read_text(encoding="utf8"))
name_to_label = {n: i + 1 for i, n in enumerate(names)}
for part_name, whole_name in overrides.get("merge", {}).items():
    geo[geo == name_to_label[part_name]] = name_to_label[whole_name]
forced = {}  # region id -> label (0 = sea)
for x, y, country in overrides.get("regions", []):
    r = int(regions[y, x])
    if r < 0 or r in water_ids:
        print(f"overrides.json: ({x}, {y}) for {country} is not inside a drawn land region")
        continue
    if country is not None and country not in name_to_label:
        print(f"overrides.json: unknown country {country!r}")
        continue
    forced[r] = name_to_label[country] if country else 0

# In the ocean and enclosed seas, real land only counts close to something drawn
# (a leaky coastline, a dotted island), not where the artist drew plain sea.
ink_parts, ink_count = components(ink & dilate(water, 2) & ~dilate(land_cell, 3))
dots = np.zeros(ink_count, dtype=bool)
iy, ix = np.nonzero(ink_parts >= 0)
part = ink_parts[iy, ix]
part_size = np.bincount(part, minlength=ink_count)
for p_id in np.flatnonzero((part_size >= 4) & (part_size <= 200)):
    py, px = iy[part == p_id], ix[part == p_id]
    h_, w_ = np.ptp(py) + 1, np.ptp(px) + 1
    if max(h_, w_) > 20 or len(py) / (h_ * w_) <= 0.45:
        continue  # not a compact blob
    # A drawn island stands clear of other pen strokes; waves come in bundles.
    y0_, y1_ = max(py.min() - 6, 0), min(py.max() + 7, H)
    x0_, x1_ = max(px.min() - 6, 0), min(px.max() + 7, W)
    around = ink[y0_:y1_, x0_:x1_].sum() - len(py)
    dots[p_id] = around < 0.12 * ((y1_ - y0_) * (x1_ - x0_) - len(py))
dot_ink = (ink_parts >= 0) & dots[np.maximum(ink_parts, 0)]
near_drawn = dilate(coast_ink | border_ink, OCEAN_LAND_REACH) | dilate(dot_ink, 4)
result = np.where(water & near_drawn, geo, 0).astype(np.uint8)
flat_regions = regions.ravel()
flat_geo = geo.ravel()
flat_result = result.ravel()

# For drawn regions with little real land under them: which country is nearest.
land_sy, land_sx, land_d2 = nearest_site(geo > 0)
flat_nearest = geo[land_sy.clip(0, H - 1), land_sx.clip(0, W - 1)].ravel()
flat_land_dist = np.sqrt(land_d2).ravel()
def assign(members):
    """Which country each pixel of one drawn region belongs to (None: leave as sea)."""
    votes = np.bincount(flat_geo[members], minlength=len(countries) + 1)
    if votes[0] > 0.6 * len(members):
        # Mostly sea in real life. Far from any real land it's a drawn inland
        # sea (Caspian, Black Sea); otherwise the drawing is just offset (a
        # fjord coast, a small island), so it goes to the nearest country.
        if np.median(flat_land_dist[members]) > LAKE_DIST:
            return None
        near = np.bincount(flat_nearest[members], minlength=len(countries) + 1)
        near[0] = 0
        return near.argmax()
    land = votes.copy()
    land[0] = 0
    ranked = np.argsort(land)[::-1]
    top, second = ranked[0], ranked[1]
    if land[second] >= MIXED_SHARE * land.sum() and len(members) > 150:
        labels = flat_geo[members]
        return np.where(labels == 0, top, labels)
    return top


def grouped(pixels, ids):
    """Split flat pixel indices into runs sharing the same id."""
    pixels = pixels[np.argsort(ids[pixels], kind="stable")]
    keys = ids[pixels]
    starts = np.flatnonzero(np.r_[True, keys[1:] != keys[:-1]]) if len(keys) else []
    ends = np.r_[starts[1:], len(keys)] if len(keys) else []
    return [(int(keys[a]), pixels[a:b]) for a, b in zip(starts, ends)]


for r, members in grouped(np.flatnonzero((flat_regions >= 0) & ~water.ravel()), flat_regions):
    if r in forced:
        flat_result[members] = forced[r]
        continue
    labels = assign(members)
    if labels is not None:
        flat_result[members] = labels

# Islands whose outlines have small gaps leak into the sea region. Sealing
# wider gaps closes them; each is then matched like any other drawn region.
wide, _ = components(~((dilate(ink, SEAL_WIDE) & ~decoration) | wall))
wide_water = {int(wide[y, x]) for x, y in OCEAN_SEEDS + list(WATER_SEEDS.values()) if wide[y, x] >= 0}
leaky = water & (wide >= 0) & ~np.isin(wide, list(wide_water))
for _, members in grouped(np.flatnonzero(leaky.ravel()), wide.ravel()):
    # Sealing wide gaps also cuts bays and straits off the sea; only count it
    # as an island if there's real land under it.
    if len(members) < 6 or (flat_geo[members] > 0).mean() < LEAKY_LAND:
        continue
    labels = assign(members)
    flat_result[members] = 0 if labels is None else labels

# Real land lying in the sea right next to that same country's drawn land is
# just the two coastlines disagreeing: the drawing wins. (Leaky coastlines and
# dotted islands have no drawn region of their own nearby, so they stay.)
drawn_cells = (land_cell.ravel() & (flat_result != 0)).reshape(H, W)
cell_sy, cell_sx, cell_d2 = nearest_site(drawn_cells)
nearest_cell_label = result[cell_sy.clip(0, H - 1), cell_sx.clip(0, W - 1)]
spill = water & (result != 0) & (result == nearest_cell_label) & (cell_d2 <= SPILL_REACH ** 2) & ~dilate(dot_ink, 2)
result[spill] = 0

# Countries the artwork doesn't really draw get their real shape. Landlocked
# ones (Luxembourg, Andorra...) go on top of their drawn neighbours; islands
# (Isle of Man...) only where nothing else is drawn.
real = np.bincount(flat_geo, minlength=len(countries) + 1)
got = np.bincount(flat_result, minlength=len(countries) + 1)
pinned = set(forced.values())
drawn_land = (land_cell.ravel()) & (flat_result != 0)
for i in range(1, len(countries) + 1):
    if real[i] and got[i] < MIN_KEEP * real[i] and i not in pinned:
        where = flat_geo == i
        if not has_border[i - 1]:
            where &= ~drawn_land
        flat_result[where] = i

# Hand-traced areas, for places the ink can't settle (see overrides.json).
for area_def in overrides.get("areas", []):
    country = area_def["country"]
    mask_img = Image.new("1", (W, H), 0)
    ImageDraw.Draw(mask_img).polygon([tuple(p) for p in area_def["outline"]], fill=1)
    inside_area = np.array(mask_img).ravel()
    if area_def.get("mode") == "relabel":
        # Only what's drawn inside the outline (ink, land), never open sea.
        inside_area &= (flat_result != 0) | sealed.ravel()
    if area_def.get("mode") == "remove":
        # Take this country out of the outline (it was pulled onto a neighbour).
        flat_result[inside_area & (flat_result == name_to_label[country])] = 0
        continue
    flat_result[inside_area] = name_to_label[country] if country else 0

# Pen lines (and the gap-sealing band) belong to the land beside them.
fill = sealed & ~water
for _ in range(INK_REACH):
    grow = result.copy()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        shifted = np.roll(result, (dy, dx), axis=(0, 1))
        take = (grow == 0) & fill & (shifted != 0)
        grow[take] = shifted[take]
    result = grow

Image.fromarray(result, mode="L").save(ROOT / "data/hitmap.png", optimize=True)

# A label point per country: the pixel of its area nearest the area's centre.
label_points = {}
ys, xs = np.nonzero(result)
values = result[ys, xs]
for i in np.unique(values):
    sel = values == i
    cx, cy = xs[sel].mean(), ys[sel].mean()
    k = np.argmin((xs[sel] - cx) ** 2 + (ys[sel] - cy) ** 2)
    label_points[names[i - 1]] = [int(xs[sel][k]), int(ys[sel][k])]

(ROOT / "data/hitmap.json").write_text(
    json.dumps({"width": W, "height": H, "names": names, "labelPoints": label_points}, ensure_ascii=False),
    encoding="utf8",
)

# For review_hitmap.py --borders.
np.save(CACHE / "snapped.npy", verts)
np.save(CACHE / "base.npy", base_verts)
(CACHE / "rings.json").write_text(json.dumps([r[3:] for r in rings]))
np.save(CACHE / "regions.npy", regions)
np.save(CACHE / "ocean.npy", water)
np.save(CACHE / "geo.npy", geo)
print(f"{region_count} drawn regions, {len(label_points)} countries on the hit map")
