"""Race calendar (data/results/schedule.csv, fetched from Jolpica)."""
from __future__ import annotations

import csv
from pathlib import Path

FIELDS = ["season", "round", "race", "circuit", "date", "time", "quali_date", "quali_time", "sprint"]


def parse_schedule(payload: dict) -> list[dict]:
    rows = []
    for r in payload["MRData"]["RaceTable"]["Races"]:
        q = r.get("Qualifying") or {}
        rows.append({
            "season": int(r["season"]), "round": int(r["round"]), "race": r["raceName"],
            "circuit": r["Circuit"]["circuitId"], "date": r["date"], "time": r.get("time", ""),
            "quali_date": q.get("date", ""), "quali_time": q.get("time", ""),
            "sprint": "1" if r.get("Sprint") else "",
        })
    return rows


def write_schedule(path: Path, rows: list[dict]) -> None:
    path = Path(path)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["season"], r["round"])))


def read_schedule(path: Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    with open(path, newline="") as f:
        out = []
        for r in csv.DictReader(f):
            r["season"], r["round"] = int(r["season"]), int(r["round"])
            out.append(r)
        return out


def next_race(rows: list[dict], today: str) -> dict | None:
    """First race on or after `today` (ISO date), or None."""
    upcoming = sorted((r for r in rows if r["date"] >= today), key=lambda r: (r["season"], r["round"]))
    return upcoming[0] if upcoming else None
