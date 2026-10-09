"""Circuit outlines for the site, drawn from real car positions, and the circuit id of each race."""
from __future__ import annotations

import math
from pathlib import Path

from evaluation.jolpica import read_rows
from .schedule import read_schedule


def outline(xs: list[float], ys: list[float], rotation: float = 0.0, points: int = 140, width: int = 1000) -> dict:
    """Turn one lap of (x, y) car positions into a compact closed outline.

    Rotates by `rotation` degrees (FastF1 supplies each circuit's usual orientation), flips y so the shape is not
    mirrored on screen, resamples to `points` evenly spaced along the lap, and scales to `width` wide.
    Returns {"d": SVG path, "w": width, "h": height, "start": [x, y]}."""
    if len(xs) != len(ys) or len(xs) < 20:
        raise ValueError("need one lap of positions (at least 20 samples)")
    th = math.radians(rotation)
    c, s = math.cos(th), math.sin(th)
    pts = [(x * c - y * s, -(x * s + y * c)) for x, y in zip(xs, ys)]
    # distance along the lap, then resample at equal spacing so straights and corners look right
    dist = [0.0]
    for a, b in zip(pts, pts[1:]):
        dist.append(dist[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = dist[-1] or 1.0
    out, j = [], 0
    for k in range(points):
        target = total * k / points
        while j < len(dist) - 2 and dist[j + 1] < target:
            j += 1
        span = (dist[j + 1] - dist[j]) or 1.0
        f = (target - dist[j]) / span
        out.append((pts[j][0] + f * (pts[j + 1][0] - pts[j][0]), pts[j][1] + f * (pts[j + 1][1] - pts[j][1])))
    xs2, ys2 = [p[0] for p in out], [p[1] for p in out]
    x0, y0 = min(xs2), min(ys2)
    scale = width / ((max(xs2) - x0) or 1.0)
    h = ((max(ys2) - y0) * scale)
    if h > width * 1.4:                       # very tall circuit: fit the height instead
        scale = width * 1.4 / ((max(ys2) - y0) or 1.0)
        h = width * 1.4
        width_used = (max(xs2) - x0) * scale
    else:
        width_used = width
    norm = [(round((x - x0) * scale), round((y - y0) * scale)) for x, y in out]
    d = "M" + "L".join(f"{x} {y}" for x, y in norm) + "Z"
    return {"d": d, "w": round(width_used), "h": round(h), "start": list(norm[0])}


def circuit_lookup(results_dir: Path) -> dict[tuple[int, int], str]:
    """(season, round) -> circuit id, from the results and the calendar."""
    out = {}
    for r in read_rows(Path(results_dir) / "races.csv"):
        if r.get("circuit"):
            out[(r["season"], r["round"])] = r["circuit"]
    for r in read_schedule(Path(results_dir) / "schedule.csv"):
        if r.get("circuit"):
            out.setdefault((r["season"], r["round"]), r["circuit"])
    return out
