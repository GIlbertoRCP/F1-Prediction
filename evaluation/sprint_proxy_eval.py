"""Could the order the sprint started in stand in for the race grid, before Saturday qualifying exists?

For every past sprint weekend we forecast the Grand Prix three ways, each time using only earlier races:
  * real grid      the production model fed the real race grid (what the site shows after qualifying),
  * sprint grid    the same model fed the sprint's starting order instead,
  * form only      the championship model's form-only logit (no grid at all).
Writes reports/sprint_proxy.md and data/sprint_proxy.json.
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import replace
from pathlib import Path

from oracle import engine
from evaluation.data import load_races
from evaluation.jolpica import read_rows
from evaluation.season import fit_form_model
from evaluation.ordered import ScaledPL  # noqa: F401  (imported so the model code is part of the hash)

ROOT = Path(__file__).resolve().parent.parent
FLOOR = 1e-4


def sprint_grids(results_dir: Path) -> dict[tuple[int, int], dict[str, int]]:
    out: dict[tuple[int, int], dict[str, int]] = {}
    for r in read_rows(results_dir / "sprints.csv"):
        g = r.get("grid")
        out.setdefault((r["season"], r["round"]), {})[r["driver_id"]] = int(g) if str(g).isdigit() else 0
    return out


def with_grid(race, grid: dict[str, int]):
    """The same race with the sprint's starting order as the grid (0 / missing = back of the field)."""
    n = len(race.entries)
    entries = []
    for e in race.entries:
        g = grid.get(e.driver_id, 0)
        entries.append(replace(e, grid=g if g > 0 else n))
    return replace(race, entries=entries)


def ll(p: float) -> float:
    return -math.log(max(p, FLOOR))


def summarise(xs: list[float], seed: int = 1) -> tuple[float, float, float]:
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(2000))
    return sum(xs) / len(xs), means[50], means[1949]


def main() -> None:
    results = ROOT / "data" / "results"
    races = load_races(results)
    grids = sprint_grids(results)
    rows = []
    for i, race in enumerate(races):
        if race.key not in grids or i < engine.MIN_TRAIN or race.winner_id is None:
            continue
        hist = races[:i]
        w = race.winner_id
        real = engine.forecast(hist, race)
        spr = engine.forecast(hist, with_grid(race, grids[race.key]))
        util, scales = fit_form_model(hist, hist[-1])
        field = [e.driver_id for e in race.entries]
        z = {d: math.exp(util.get(d, min(util.values()))) for d in field}
        tot = sum(z.values())
        form = {d: z[d] / tot for d in field}
        top = lambda p: max(p, key=p.get)
        rows.append({"season": race.season, "round": race.round, "race": race.name, "winner": w,
                     "real": ll(real[w]), "sprint": ll(spr[w]), "form": ll(form[w]),
                     "hit_real": top(real) == w, "hit_sprint": top(spr) == w, "hit_form": top(form) == w})
    n = len(rows)
    out = {"n": n}
    for k in ("real", "sprint", "form"):
        m, lo, hi = summarise([r[k] for r in rows])
        out[k] = {"logloss": m, "lo": lo, "hi": hi, "top_pick": sum(r["hit_" + k] for r in rows) / n}
    for a, b in (("sprint", "form"), ("sprint", "real")):
        d = [r[a] - r[b] for r in rows]
        m, lo, hi = summarise(d)
        out[f"{a}_minus_{b}"] = {"mean": m, "lo": lo, "hi": hi}
    out["rows"] = rows
    (ROOT / "data" / "sprint_proxy.json").write_text(json.dumps(out, indent=1))
    lines = [f"# Sprint order as a stand-in for the race grid", "",
             f"{n} sprint weekends, walk-forward (each forecast uses only earlier races). Winner log loss, lower is better; "
             "95% bootstrap interval in brackets.", "",
             "| Forecast | Log loss | Top pick right |", "|---|---|---|"]
    for k, label in (("real", "Real race grid (after qualifying)"), ("sprint", "Sprint starting order as grid"),
                     ("form", "Form only, no grid")):
        o = out[k]
        lines.append(f"| {label} | {o['logloss']:.3f} [{o['lo']:.3f}, {o['hi']:.3f}] | {o['top_pick']:.0%} |")
    lines += ["", "Paired differences in log loss (negative = first is better):", ""]
    for key, label in (("sprint_minus_form", "sprint grid minus form only"), ("sprint_minus_real", "sprint grid minus real grid")):
        o = out[key]
        lines.append(f"* {label}: {o['mean']:+.3f} [{o['lo']:+.3f}, {o['hi']:+.3f}]")
    (ROOT / "reports" / "sprint_proxy.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
