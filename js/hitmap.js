// Which country is under each pixel of the artwork, following the borders
// as drawn. Built offline by tools/build_hitmap.py: each pixel of
// data/hitmap.png holds 1 + an index into hitmap.json's `names` (0 = sea).

export async function loadHitmap() {
  const [info, img] = await Promise.all([
    fetch("data/hitmap.json").then((r) => r.json()),
    loadImage("data/hitmap.png"),
  ]);
  const { width, height } = info;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(img, 0, 0);
  const rgba = ctx.getImageData(0, 0, width, height).data;

  const labels = new Uint8Array(width * height);
  const boxes = new Map(); // label -> [minX, minY, maxX, maxY]
  for (let i = 0, y = 0; y < height; y++) {
    for (let x = 0; x < width; x++, i++) {
      const v = rgba[i * 4];
      labels[i] = v;
      if (!v) continue;
      const b = boxes.get(v);
      if (!b) boxes.set(v, [x, y, x, y]);
      else {
        if (x < b[0]) b[0] = x;
        if (x > b[2]) b[2] = x;
        if (y < b[1]) b[1] = y;
        if (y > b[3]) b[3] = y;
      }
    }
  }

  const labelOf = new Map(info.names.map((name, i) => [name, i + 1]));
  const masks = new Map();

  return {
    labelPoints: info.labelPoints,

    nameAt(x, y) {
      x = Math.floor(x);
      y = Math.floor(y);
      if (x < 0 || y < 0 || x >= width || y >= height) return null;
      const v = labels[y * width + x];
      return v ? info.names[v - 1] : null;
    },

    // A tinted, outlined picture of one country's area, cropped to its bounds.
    mask(name, { fill = [139, 26, 16, 90], edge = [94, 15, 8, 230] } = {}) {
      const key = `${name}|${fill}|${edge}`;
      if (masks.has(key)) return masks.get(key);
      const v = labelOf.get(name);
      const box = v && boxes.get(v);
      if (!box) return null;
      const [x0, y0, x1, y1] = box;
      const w = x1 - x0 + 1;
      const h = y1 - y0 + 1;
      const c = document.createElement("canvas");
      c.width = w;
      c.height = h;
      const cctx = c.getContext("2d");
      const out = cctx.createImageData(w, h);
      for (let y = y0; y <= y1; y++) {
        for (let x = x0; x <= x1; x++) {
          const i = y * width + x;
          if (labels[i] !== v) continue;
          const isEdge =
            x === 0 || y === 0 || x === width - 1 || y === height - 1 ||
            labels[i - 1] !== v || labels[i + 1] !== v || labels[i - width] !== v || labels[i + width] !== v;
          const color = isEdge ? edge : fill;
          const o = ((y - y0) * w + (x - x0)) * 4;
          out.data[o] = color[0];
          out.data[o + 1] = color[1];
          out.data[o + 2] = color[2];
          out.data[o + 3] = color[3];
        }
      }
      cctx.putImageData(out, 0, 0);
      const mask = { href: c.toDataURL(), x: x0, y: y0, width: w, height: h };
      masks.set(key, mask);
      return mask;
    },
  };
}

function loadImage(src) {
  const img = new Image();
  img.src = src;
  return img.decode().then(() => img);
}
