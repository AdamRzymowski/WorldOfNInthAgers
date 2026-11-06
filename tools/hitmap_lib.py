"""Image helpers shared by build_hitmap.py and build_minimap.py."""

from collections import deque

import numpy as np


def disk_offsets(r):
    return [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dy * dy + dx * dx <= r * r]


def dilate(mask, r):
    out = mask.copy()
    for dy, dx in disk_offsets(r):
        if dy or dx:
            out |= np.roll(mask, (dy, dx), axis=(0, 1))
    return out


def components(free):
    """4-connected components of True pixels. Returns (labels, count); -1 where False."""
    h, w = free.shape
    flat = free.ravel()
    lab = np.full(h * w, -1, dtype=np.int32)
    n = 0
    for start in np.flatnonzero(flat):
        if lab[start] != -1:
            continue
        lab[start] = n
        queue = deque([start])
        while queue:
            p = queue.popleft()
            y, x = divmod(p, w)
            for q, ok in ((p - 1, x > 0), (p + 1, x < w - 1), (p - w, y > 0), (p + w, y < h - 1)):
                if ok and flat[q] and lab[q] == -1:
                    lab[q] = n
                    queue.append(q)
        n += 1
    return lab.reshape(h, w), n


def nearest_site(sites):
    """Jump flooding: for every pixel, the coordinates of (and squared distance to) the nearest True pixel."""
    h, w = sites.shape
    ys, xs = np.mgrid[0:h, 0:w]
    sy = np.where(sites, ys, -10**6).astype(np.int32)
    sx = np.where(sites, xs, -10**6).astype(np.int32)
    best = np.where(sites, 0, np.iinfo(np.int64).max).astype(np.int64)
    step = 1 << int(np.ceil(np.log2(max(h, w))))
    while step >= 1:
        for dy in (-step, 0, step):
            for dx in (-step, 0, step):
                if not dy and not dx:
                    continue
                cy = np.roll(sy, (dy, dx), axis=(0, 1))
                cx = np.roll(sx, (dy, dx), axis=(0, 1))
                d = (cy.astype(np.int64) - ys) ** 2 + (cx.astype(np.int64) - xs) ** 2
                better = d < best
                best[better] = d[better]
                sy[better] = cy[better]
                sx[better] = cx[better]
        step //= 2
    return sy, sx, best
