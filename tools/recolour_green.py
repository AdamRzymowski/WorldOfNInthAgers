"""Repaints a minimap's gold featured country as grassy green, like the
Romania and United Kingdom maps were drawn.

    python recolour_green.py ../data/country-maps/poland.json [more configs...]

Only pixels inside the featured country (from its built hit map, plus a few
pixels for its outline) with a gold-to-brown hue are changed: hue is moved to
the green of the Romania map and value and saturation are matched to it, so
ink, trees, rivers and lakes keep their drawing. The gold version is kept as
assets/country-maps/gold/<name>.webp and is always the starting point, so
re-running is safe; build_minimap.py reads that copy when it exists, so the
gold detection keeps working. Run after repaint_land.py, which writes the
image from its own originals.
"""

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from hitmap_lib import dilate

ROOT = Path(__file__).resolve().parent.parent

# Romania's land in PIL's 0-255 HSV: median hue, saturation and value.
TARGET_H, TARGET_S, TARGET_V = 40, 235, 190

# Crest and name, compass, title, dragons, globe (fractions, as in build_minimap.py).
DECOR = [(0.05, 0.08, 0.315, 0.44), (0.03, 0.44, 0.165, 0.76), (0.27, 0, 0.74, 0.10),
         (0, 0, 0.16, 0.20), (0.84, 0, 1, 0.19), (0.455, 0.88, 0.545, 1)]


def recolour(config_path):
    cfg = json.loads(config_path.read_text(encoding="utf8"))
    image_path = ROOT / cfg["image"]
    gold = ROOT / "assets/country-maps/gold" / image_path.name
    gold.parent.mkdir(parents=True, exist_ok=True)
    if not gold.exists():
        shutil.copy(image_path, gold)

    art = Image.open(gold).convert("RGB")
    hsv = np.asarray(art.convert("HSV")).astype(float)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    hitmap = np.asarray(Image.open(config_path.with_name(f"{config_path.stem}-hitmap.png")))
    names = json.loads(config_path.with_name(f"{config_path.stem}-hitmap.json").read_text(encoding="utf8"))["names"]
    featured = hitmap == names.index(cfg["country"]) + 1

    # Gold, ochre and brown ink count; blue water and grey ink do not.
    golden = (h >= 8) & (h <= 48) & (s >= 60)

    # The hit map leaves decorations blank, so land of the featured country
    # under the crest's box is missing from it: spread into bright gold that
    # touches the country there without crossing ink, then take in the drawing on it.
    H, W = h.shape
    reach = Image.new("1", (W, H), 0)
    ImageDraw.Draw(reach).rectangle([0.2 * W, 0.08 * H, 0.315 * W, 0.44 * H], fill=1)  # right part of the crest's box
    open_gold = np.asarray(reach) & (hitmap == 0) & (h >= 20) & (h <= 38) & (s >= 150) & (v > 170)
    grown = featured.copy()
    for _ in range(600):
        step = grown.copy()
        step[1:] |= grown[:-1]
        step[:-1] |= grown[1:]
        step[:, 1:] |= grown[:, :-1]
        step[:, :-1] |= grown[:, 1:]
        step &= open_gold | featured
        if (step == grown).all():
            break
        grown = step
    inside = dilate(featured, 3) | (dilate(grown & ~featured, 6) & (hitmap == 0))
    core = inside & golden & (v > 150)
    med_h, med_s, med_v = (np.median(c[core]) for c in (h, s, v))
    print(f"{config_path.stem}: gold median h={med_h:.0f} s={med_s:.0f} v={med_v:.0f}")

    weight = (inside & golden).astype(np.float32)
    weight *= np.clip((s - 60) / 60, 0, 1)  # fade out on near-grey pixels
    weight = np.asarray(Image.fromarray((weight * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255.0
    weight *= inside

    new_h = np.clip(h + (TARGET_H - med_h), 0, 255)
    new_s = np.clip(s * (TARGET_S / max(med_s, 1)), 0, 255)
    new_v = np.clip(v * (TARGET_V / max(med_v, 1)), 0, 255)
    green = np.stack([new_h, new_s, new_v], axis=-1).astype(np.uint8)
    green = np.asarray(Image.fromarray(green, "HSV").convert("RGB")).astype(float)

    # Gold the artist gave to neighbours (Northern Ireland on Ireland's map,
    # Cyprus on Turkey's) fades to the neighbours' parchment instead, so only
    # the featured country stands out.
    neighbour = (hitmap > 0) & ~inside
    plain = neighbour & (s < 140) & (v > 150)
    if not plain.any():  # no neighbours drawn (Australia)
        plain = neighbour = np.zeros_like(inside)
        par_h = par_s = par_v = 0
    else:
        par_h, par_s, par_v = (np.median(c[plain]) for c in (h, s, v))
    # Gold left unlabelled (pieces the hit map never claimed) fades too, away
    # from the frame and the standard decorations.
    loose = Image.new("1", (W, H), 0)
    ImageDraw.Draw(loose).rectangle([0.05 * W, 0.05 * H, 0.95 * W, 0.93 * H], fill=1)
    for x0, y0, x1, y1 in DECOR:
        ImageDraw.Draw(loose).rectangle([x0 * W, y0 * H, x1 * W, y1 * H], fill=0)
    loose = np.asarray(loose) & (hitmap == 0) & ~inside
    neighbour |= loose
    foreign = neighbour & golden & (s >= 150) & (v > 170)
    fade = np.asarray(Image.fromarray((foreign * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255.0
    fade *= neighbour
    parchment = np.stack([np.full_like(h, par_h), s * (par_s / max(med_s, 1)), v * (par_v / max(med_v, 1))], axis=-1)
    parchment = np.asarray(Image.fromarray(parchment.clip(0, 255).astype(np.uint8), "HSV").convert("RGB")).astype(float)

    px = np.asarray(art).astype(float)
    out = px * (1 - weight[..., None]) + green * weight[..., None]
    out = out * (1 - fade[..., None]) + parchment * fade[..., None]
    Image.fromarray(out.clip(0, 255).astype(np.uint8)).save(image_path, quality=92, method=6)
    print(f"  wrote {image_path.relative_to(ROOT)}")


for arg in sys.argv[1:]:
    recolour(Path(arg).resolve())
