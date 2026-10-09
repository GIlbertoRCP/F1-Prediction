"""Practice-session pace features, computed from lap records.

Only sessions that finish before the race's qualifying session count, so every feature here is
known before the starting grid is. The functions take plain lap records (dicts), so the maths can be
tested without FastF1; scripts/extract_practice_features.py does the FastF1 download and conversion.

A lap record has: driver, team, lap_time (seconds or None), compound, stint, in_lap, out_lap,
track_clear (green track, no yellow flag), deleted.
"""
from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path

GAP_CAP = 5.0          # percent
MIN_DRIVERS = 10       # a session with fewer drivers setting clean laps (red-flagged, washed out) is ignored
MIN_STINT_LAPS = 5     # clean laps in one stint to count as a long run
MIN_DRIVERS_PER_COMPOUND = 3

FIELDS = ["season", "round", "race", "driver", "team", "fp_gap", "fp_long", "fp_sessions", "fp_laps"]


def clean_laps(laps: list[dict]) -> list[dict]:
    return [l for l in laps if l.get("lap_time") and l["lap_time"] > 0 and l.get("track_clear")
            and not l.get("in_lap") and not l.get("out_lap") and not l.get("deleted")]


def session_features(laps: list[dict]) -> dict[str, dict]:
    """Per driver: best clean lap gap (%) to the session's fastest, and long-run pace gap (%)
    to the best long run on the same tyre compound. None where it cannot be measured."""
    good = clean_laps(laps)
    best: dict[str, float] = {}
    team: dict[str, str] = {}
    for l in good:
        best[l["driver"]] = min(best.get(l["driver"], 1e9), l["lap_time"])
    for l in laps:
        team.setdefault(l["driver"], l.get("team", ""))
    if len(best) < MIN_DRIVERS:
        return {}
    fastest = min(best.values())
    out = {d: {"team": team.get(d, ""), "gap": min((t / fastest - 1) * 100, GAP_CAP), "long": None,
               "laps": sum(1 for l in good if l["driver"] == d)} for d, t in best.items()}

    stints: dict[tuple[str, object], list[dict]] = defaultdict(list)
    for l in good:
        stints[(l["driver"], l.get("stint"))].append(l)
    medians: dict[str, dict[str, float]] = defaultdict(dict)   # compound -> driver -> best median
    for (d, _), ls in stints.items():
        compound = ls[0].get("compound") or "UNKNOWN"
        if len(ls) >= MIN_STINT_LAPS and compound not in ("UNKNOWN", "nan", "TEST_UNKNOWN"):
            med = statistics.median(l["lap_time"] for l in ls)
            medians[compound][d] = min(med, medians[compound].get(d, 1e9))
    longs: dict[str, list[float]] = defaultdict(list)
    for compound, drivers in medians.items():
        if len(drivers) < MIN_DRIVERS_PER_COMPOUND:
            continue
        ref = min(drivers.values())
        for d, med in drivers.items():
            longs[d].append(min((med / ref - 1) * 100, GAP_CAP))
    for d, vals in longs.items():
        if d in out:
            out[d]["long"] = min(vals)
    return out


def weekend_features(sessions: list[list[dict]]) -> dict[str, dict]:
    """Combine the pre-qualifying practice sessions of one weekend: best gap over sessions, mean
    long-run gap over the sessions where one was measured."""
    gaps: dict[str, list[float]] = defaultdict(list)
    longs: dict[str, list[float]] = defaultdict(list)
    info: dict[str, dict] = {}
    for laps in sessions:
        for d, f in session_features(laps).items():
            gaps[d].append(f["gap"])
            if f["long"] is not None:
                longs[d].append(f["long"])
            e = info.setdefault(d, {"team": f["team"], "laps": 0})
            e["laps"] += f["laps"]
    return {d: {"team": info[d]["team"], "fp_gap": min(gaps[d]),
                "fp_long": (sum(longs[d]) / len(longs[d])) if longs[d] else None,
                "fp_sessions": len(gaps[d]), "fp_laps": info[d]["laps"]} for d in gaps}


def read_practice(path: Path) -> dict[tuple[int, int], dict[str, tuple[float | None, float | None]]]:
    """(season, round) -> driver code -> (fp_gap, fp_long)."""
    path = Path(path)
    out: dict = {}
    if not path.exists():
        return out
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            key = (int(r["season"]), int(r["round"]))
            out.setdefault(key, {})[r["driver"]] = (
                float(r["fp_gap"]) if r["fp_gap"] != "" else None,
                float(r["fp_long"]) if r["fp_long"] != "" else None)
    return out
