"""Renders a zoomed, labelled view of the hit map for checking it by eye.

    python review_hitmap.py NAME X0 Y0 X1 Y1 [SCALE] [--borders]

Writes tools/.cache/review/NAME.png: the artwork, each country's area tinted
and labelled, plus a grid in artwork pixels (every 10, labelled every 50) so
you can read off coordinates for overrides.json. --borders also draws the
real borders as snapped onto the artwork (thin red).
"""

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
args = [a for a in sys.argv[1:] if not a.startswith("--")]
show_borders = "--borders" in sys.argv
name, x0, y0, x1, y1 = args[0], *map(int, args[1:5])
scale = int(args[5]) if len(args) > 5 else 3

labels = np.asarray(Image.open(ROOT / "data/hitmap.png"))
names = json.loads((ROOT / "data/hitmap.json").read_text(encoding="utf8"))["names"]
art = np.asarray(Image.open(ROOT / "assets/world-map.webp").convert("RGB")).astype(float)
crop_l = labels[y0:y1, x0:x1]

# Map colouring: neighbouring countries always get clearly different colours.
COLOURS = np.array([(230, 25, 75), (60, 180, 75), (0, 130, 200), (245, 130, 48), (145, 30, 180),
                    (70, 240, 240), (240, 50, 230), (210, 245, 60), (128, 128, 0), (0, 0, 128)])
adjacent = {}
for a_, b_ in ((crop_l[:, :-1], crop_l[:, 1:]), (crop_l[:-1, :], crop_l[1:, :])):
    for u, v in set(zip(a_.ravel().tolist(), b_.ravel().tolist())):
        if u != v and u and v:
            adjacent.setdefault(u, set()).add(v)
            adjacent.setdefault(v, set()).add(u)
colour_of = {}
for v in sorted(adjacent, key=lambda v: -len(adjacent[v])) + [v for v in np.unique(crop_l).tolist() if v not in adjacent]:
    used = {colour_of.get(n) for n in adjacent.get(v, ())}
    colour_of[v] = next(i for i in range(len(COLOURS)) if i not in used)
palette = np.zeros((256, 3))
for v, c in colour_of.items():
    palette[v] = COLOURS[c]

crop_a = art[y0:y1, x0:x1]
tinted = np.where((crop_l > 0)[..., None], crop_a * 0.5 + palette[crop_l] * 0.5, crop_a)
img = Image.fromarray(tinted.astype(np.uint8)).resize(((x1 - x0) * scale, (y1 - y0) * scale), Image.NEAREST)
d = ImageDraw.Draw(img)

for x in range((x0 // 10 + 1) * 10, x1, 10):
    X = (x - x0) * scale
    d.line([(X, 0), (X, img.height)], fill=(255, 0, 0) if x % 50 == 0 else (90, 90, 255), width=1)
    if x % 50 == 0:
        d.text((X + 2, 2), str(x), fill=(255, 0, 0))
for y in range((y0 // 10 + 1) * 10, y1, 10):
    Y = (y - y0) * scale
    d.line([(0, Y), (img.width, Y)], fill=(255, 0, 0) if y % 50 == 0 else (90, 90, 255), width=1)
    if y % 50 == 0:
        d.text((2, Y + 2), str(y), fill=(255, 0, 0))

if show_borders:
    verts = np.load(ROOT / "tools/.cache/snapped.npy")
    for s_, e_ in json.loads((ROOT / "tools/.cache/rings.json").read_text()):
        pts = [((x - x0) * scale, (y - y0) * scale) for x, y in verts[s_:e_]]
        d.line(pts, fill=(200, 0, 0), width=1)

# Label every separate piece of every country in view.
font = ImageFont.load_default(size=max(11, 4 * scale))
seen = np.zeros_like(crop_l, dtype=bool)
h, w = crop_l.shape
for v in np.unique(crop_l):
    if v == 0:
        continue
    mask = crop_l == v
    # crude piece split: label connected chunks via flood fill on the mask
    todo = mask & ~seen
    while todo.any():
        sy, sx = np.argwhere(todo)[0]
        stack = [(sy, sx)]
        piece = []
        seen[sy, sx] = True
        while stack:
            cy, cx = stack.pop()
            piece.append((cy, cx))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        todo = mask & ~seen
        if len(piece) < 40:
            continue
        ys, xs = np.array(piece).T
        cy, cx = ys.mean(), xs.mean()
        k = np.argmin((ys - cy) ** 2 + (xs - cx) ** 2)
        tx, ty = xs[k] * scale, ys[k] * scale
        text = names[v - 1][:14]
        d.text((tx, ty), text, fill=(0, 0, 0), font=font, anchor="mm", stroke_width=3, stroke_fill=(255, 255, 255))

out = ROOT / "tools/.cache/review"
out.mkdir(parents=True, exist_ok=True)
img.save(out / f"{name}.png")
print(out / f"{name}.png", img.size)
