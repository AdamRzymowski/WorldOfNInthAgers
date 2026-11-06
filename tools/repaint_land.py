"""Repaints part of a minimap as plain land, for sea the artist drew by mistake.

    python repaint_land.py ../data/country-maps/czechia.json

Reads "repaint": [{"outline": [[x, y], ...], "keep": ["Czechia"]}] from the
config. Inside each outline, everything except the countries listed in
"keep", the standard decorations and a thin band along their edges (so drawn
border lines survive) is covered with parchment texture taken from the
plainest patch of land on the map. Ships and clouds there are painted over.

The untouched artwork is kept as assets/country-maps/originals/<name>.webp and
is always the starting point, so re-running is safe. Rebuild the hit map
afterwards (build_minimap.py), adding an "areas" entry to make the repainted
land clickable.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from hitmap_lib import dilate

ROOT = Path(__file__).resolve().parent.parent
config_path = Path(sys.argv[1]).resolve()
cfg = json.loads(config_path.read_text(encoding="utf8"))
image_path = ROOT / cfg["image"]
original = ROOT / "assets/country-maps/originals" / image_path.name
original.parent.mkdir(parents=True, exist_ok=True)
if not original.exists():
    shutil.copy(image_path, original)

art = Image.open(original).convert("RGB")
W, H = art.size
px = np.asarray(art).astype(float)
grey = px.mean(axis=2)
hitmap = np.asarray(Image.open(config_path.with_name(f"{config_path.stem}-hitmap.png")))
names = json.loads(config_path.with_name(f"{config_path.stem}-hitmap.json").read_text(encoding="utf8"))["names"]

# Standard layout pieces stay as drawn (same fractions as build_minimap.py).
KEEP_DECOR = [(0.05, 0.08, 0.315, 0.44), (0.03, 0.44, 0.165, 0.76), (0, 0, 1, 0.035), (0, 0.95, 1, 1),
              (0, 0, 0.04, 1), (0.96, 0, 1, 1), (0.27, 0, 0.74, 0.10), (0.455, 0.88, 0.545, 1)]
decor = Image.new("1", (W, H), 0)
for x0, y0, x1, y1 in KEEP_DECOR:
    ImageDraw.Draw(decor).rectangle([x0 * W, y0 * H, x1 * W, y1 * H], fill=1)
decor = np.asarray(decor)


def box_sum(a, r):
    c = np.pad(a.astype(float), ((r + 1, r), (r + 1, r))).cumsum(0).cumsum(1)
    n = 2 * r + 1
    return c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]


# Texture source: the window of neighbouring land with the least ink in it.
featured = names.index(cfg["country"]) + 1 if cfg["country"] in names else -1
land = (hitmap > 0) & (hitmap != featured) & ~decor
size = 120
r = size // 2
ink_count = box_sum(grey < 150, r)
land_count = box_sum(land, r)
score = np.where(land_count >= 0.999 * size * size, ink_count, np.inf)
score[:r] = score[-r:] = np.inf
score[:, :r] = score[:, -r:] = np.inf
cy, cx = np.unravel_index(np.argmin(score), score.shape)
patch = px[cy - r : cy + r, cx - r : cx + r]
print(f"texture from ({cx}, {cy}), {int(ink_count[cy, cx])} ink pixels")

# Mirror-tile the patch so there are no visible seams.
tile = np.concatenate([patch, patch[:, ::-1]], axis=1)
tile = np.concatenate([tile, tile[::-1]], axis=0)
reps = (H // tile.shape[0] + 1, W // tile.shape[1] + 1, 1)
texture = np.tile(tile, reps)[:H, :W]

out = px.copy()
for job in cfg.get("repaint", []):
    area = Image.new("1", (W, H), 0)
    ImageDraw.Draw(area).polygon([tuple(p) for p in job["outline"]], fill=1)
    keep = np.isin(hitmap, [names.index(n) + 1 for n in job.get("keep", []) if n in names])
    keep = dilate(keep, job.get("margin", 7)) | decor
    mask = np.asarray(area) & ~keep
    soft = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(4))) / 255.0
    soft = np.minimum(soft, mask.astype(float) + soft * 0.5)
    out = out * (1 - soft[..., None]) + texture * soft[..., None]

Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(image_path, quality=92, method=6)
print(f"repainted {image_path.relative_to(ROOT)}")
