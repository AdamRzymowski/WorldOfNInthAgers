"""Builds data/hitmap.png: which country each pixel of the artwork belongs to.

The artwork's borders are hand-drawn and don't follow the real ones exactly,
so hit areas taken straight from real geography feel wrong when you hover
(you point inside a drawn country and its neighbour lights up). Instead we:

1. split the artwork into the regions enclosed by its ink lines,
2. give each region to the real country that covers most of it,
3. fall back to real geography where the artwork has no region of its own
   (tiny countries) or where one drawn region clearly holds two countries.

Run `node project-countries.mjs` first (or `npm run hitmap`, which does both).
Needs Python with Pillow and numpy.
"""

import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
INK = 100            # pixels darker than this are pen lines
MIXED_SHARE = 0.25   # a runner-up country this big means the region holds two countries
MIN_KEEP = 0.2       # countries left with less than this share of their real area get it back
INK_REACH = 10       # how far (px) ink (borders, drawn trees and mountains) is absorbed into the land around it

art = Image.open(ROOT / "assets/world-map.webp").convert("L")
W, H = art.size
ink = np.asarray(art) < INK

countries = json.loads((ROOT / "tools/.cache/projected.json").read_text())
names = [c["name"] for c in countries]

# Real geography, rasterised. Large countries first so enclaves land on top.
def ring_area(ring):
    xs, ys = np.array(ring).T
    return abs(np.dot(xs, np.roll(ys, 1)) - np.dot(ys, np.roll(xs, 1))) / 2

order = sorted(range(len(countries)), key=lambda i: -sum(ring_area(p[0]) for p in countries[i]["polygons"]))
geo_img = Image.new("L", (W, H), 0)
draw = ImageDraw.Draw(geo_img)
for i in order:
    for polygon in countries[i]["polygons"]:
        draw.polygon([tuple(p) for p in polygon[0]], fill=i + 1)
        for hole in polygon[1:]:
            draw.polygon([tuple(p) for p in hole], fill=0)
geo = np.asarray(geo_img).copy()

# Connected regions of parchment between the ink lines (4-connected).
regions = np.full(H * W, -1, dtype=np.int32)
free = ~ink.ravel()
count = 0
for start in np.flatnonzero(free):
    if regions[start] != -1:
        continue
    regions[start] = count
    queue = deque([start])
    while queue:
        p = queue.popleft()
        y, x = divmod(p, W)
        for q, ok in ((p - 1, x > 0), (p + 1, x < W - 1), (p - W, y > 0), (p + W, y < H - 1)):
            if ok and free[q] and regions[q] == -1:
                regions[q] = count
                queue.append(q)
    count += 1
regions = regions.reshape(H, W)

result = np.zeros((H, W), dtype=np.uint8)
flat_regions = regions.ravel()
flat_geo = geo.ravel()
inside = flat_regions >= 0
sort = np.argsort(flat_regions[inside], kind="stable")
pix = np.flatnonzero(inside)[sort]
bounds = np.searchsorted(flat_regions[pix], np.arange(count + 1))
flat_result = result.ravel()
for r in range(count):
    members = pix[bounds[r] : bounds[r + 1]]
    votes = np.bincount(flat_geo[members], minlength=len(countries) + 1)
    if votes.argmax() == 0:
        # Mostly sea. Where a coastline has a gap the land leaks into the
        # ocean region, so keep whatever real land falls inside it.
        flat_result[members] = flat_geo[members]
        continue
    land = votes.copy()
    land[0] = 0
    ranked = np.argsort(land)[::-1]
    top, second = ranked[0], ranked[1]
    if land[second] >= MIXED_SHARE * land.sum() and len(members) > 400:
        labels = flat_geo[members]
        flat_result[members] = np.where(labels == 0, top, labels)
    else:
        flat_result[members] = top

# Countries the artwork doesn't really draw get their real shape back.
real = np.bincount(flat_geo, minlength=len(countries) + 1)
got = np.bincount(flat_result, minlength=len(countries) + 1)
for i in range(1, len(countries) + 1):
    if real[i] and got[i] < MIN_KEEP * real[i]:
        flat_result[flat_geo == i] = i

# Let the ink lines themselves belong to the neighbouring country.
for _ in range(INK_REACH):
    grow = result.copy()
    for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        shifted = np.roll(result, (dy, dx), axis=(0, 1))
        take = (grow == 0) & ink & (shifted != 0)
        grow[take] = shifted[take]
    result = grow

Image.fromarray(result, mode="L").save(ROOT / "data/hitmap.png", optimize=True)

# A label point per country: the region pixel nearest its centre of mass.
labels = {}
ys, xs = np.nonzero(result)
values = result[ys, xs]
for i in np.unique(values):
    sel = values == i
    cx, cy = xs[sel].mean(), ys[sel].mean()
    k = np.argmin((xs[sel] - cx) ** 2 + (ys[sel] - cy) ** 2)
    labels[names[i - 1]] = [int(xs[sel][k]), int(ys[sel][k])]

(ROOT / "data/hitmap.json").write_text(
    json.dumps({"width": W, "height": H, "names": names, "labelPoints": labels}, ensure_ascii=False)
)
print(f"{count} drawn regions, {len(labels)} countries on the hit map")
