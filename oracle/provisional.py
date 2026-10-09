"""A provisional forecast for the next race, for the days before qualifying exists.

It is shown on the site so the page is never empty, but it is NOT part of the track record: it is not frozen
in the log and not scored. It sharpens in stages as real information arrives:

  1. "form"   nothing but recent form (the championship model's form-only logit);
  2. "sprint" on a sprint weekend, once the sprint has run: the sprint's starting order stands in for the grid;
  3. qualifying lands and the normal, frozen forecast replaces it.

How good each stage has been in past tests is stated on the page (reports/sprint_proxy.md, reports/telemetry.md).
"""
from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

from evaluation.data import Race
from evaluation.jolpica import read_rows
from evaluation.season import fit_form_model
from . import engine

STAGES = [("form", "Recent form"), ("sprint", "Sprint order"), ("quali", "Qualifying")]

NOTES = {
    "form": "Built only from recent form, with no starting grid. In past tests the form-only favourite won "
            "about 4 races in 10, against about 55% once the grid is known, so treat these odds as a rough guide.",
    "sprint": "Built from recent form plus the order the sprint started in, standing in for the real grid. "
              "On 29 past sprint weekends this picked the winner as often as the real grid (41%), but its odds were "
              "less reliable. Too few weekends to be sure it beats form alone.",
}


def _sprint_grid(results_dir: Path, key: tuple[int, int]) -> dict[str, int]:
    out = {}
    for r in read_rows(Path(results_dir) / "sprints.csv"):
        if (r["season"], r["round"]) == key:
            g = str(r.get("grid", "")).strip()
            out[r["driver_id"]] = int(g) if g.isdigit() else 0
    return out


def build(races: list[Race], results_dir: Path, nxt: dict | None) -> dict | None:
    """Provisional odds for the race described by the schedule row `nxt`, or None if we can't make them."""
    if not nxt or len(races) <= engine.MIN_TRAIN:
        return None
    lineup = races[-1]
    key = (nxt["season"], nxt["round"])
    grid = _sprint_grid(results_dir, key) if nxt.get("sprint") else {}
    if grid:
        n = len(lineup.entries)
        entries = [replace(e, grid=(grid.get(e.driver_id) or n), finish_position=None, classified=False)
                   for e in lineup.entries]
        race = Race(key[0], key[1], nxt["race"], entries, nxt.get("date", ""))
        probs = engine.forecast(races, race)
        stage = "sprint"
        shown = {e.driver_id: e.grid for e in entries}
    else:
        util, _ = fit_form_model(races, lineup)
        z = {e.driver_id: math.exp(util[e.driver_id]) for e in lineup.entries}
        tot = sum(z.values())
        probs = {d: v / tot for d, v in z.items()}
        stage = "form"
        shown = {}
    rows = [{"driver_id": e.driver_id, "driver": e.driver, "team": e.team,
             "grid": shown.get(e.driver_id), "p": round(probs[e.driver_id], 6)} for e in lineup.entries]
    rows.sort(key=lambda r: (-r["p"], r["driver_id"]))
    return {"stage": stage, "stages": [{"key": k, "label": l} for k, l in STAGES], "note": NOTES[stage],
            "race": nxt["race"], "season": key[0], "round": key[1], "predictions": rows}
