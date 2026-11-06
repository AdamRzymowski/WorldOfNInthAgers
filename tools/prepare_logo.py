"""Turns a community logo into a marker-ready image in assets/logos/.

    python prepare_logo.py SOURCE NAME [--brighten 1.6]

Makes a plain white background transparent, crops to the logo, optionally
brightens it, and pads it to a square (so round map markers don't clip it).
Writes assets/logos/NAME.webp; use that path as the community's "logo".
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent

parser = argparse.ArgumentParser()
parser.add_argument("source")
parser.add_argument("name")
parser.add_argument("--brighten", type=float, default=1.0, help="1 = unchanged, 1.5 = 50%% brighter")
parser.add_argument("--size", type=int, default=256)
args = parser.parse_args()

img = Image.open(args.source).convert("RGBA")
px = np.asarray(img).astype(float)

# Near-white pixels fade out, so anti-aliased edges stay smooth.
whiteness = np.clip((px[..., :3].min(axis=2) - 235) / 20, 0, 1)
px[..., 3] *= 1 - whiteness
img = Image.fromarray(px.astype(np.uint8))
img = img.crop(img.getbbox())

if args.brighten != 1.0:
    alpha = img.getchannel("A")
    rgb = ImageEnhance.Brightness(img.convert("RGB")).enhance(args.brighten)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.1)
    img = rgb.convert("RGBA")
    img.putalpha(alpha)

side = max(img.size)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
square = square.resize((args.size, args.size), Image.LANCZOS)

out = ROOT / "assets/logos" / f"{args.name}.webp"
square.save(out, quality=92, method=6)
print(f"wrote {out.relative_to(ROOT)}")
