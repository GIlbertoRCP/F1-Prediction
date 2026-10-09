"""Parse Jolpica/Ergast JSON payloads into flat rows, and write them as CSV."""
from __future__ import annotations

import csv
from pathlib import Path

RACE_FIELDS = [
    "season", "round", "race", "date", "circuit", "driver", "driver_id", "team",
    "grid", "finish_position", "classified", "status", "points",
]
QUALI_FIELDS = [
    "season", "round", "race", "date", "circuit", "driver", "driver_id", "team",
    "quali_position", "q1", "q2", "q3",
]
FIELDS = {"results": RACE_FIELDS, "sprint": RACE_FIELDS, "qualifying": QUALI_FIELDS}
FILENAMES = {"results": "races.csv", "sprint": "sprints.csv", "qualifying": "qualifying.csv"}


def parse_payload(kind: str, payload: dict) -> list[dict]:
    """Return flat rows for every race contained in one Jolpica response.

    kind is 'results', 'sprint' or 'qualifying'. Paginated responses may split one
    race across pages, so callers should de-duplicate on (season, round, driver_id).
    """
    rows: list[dict] = []
    for race in payload.get("MRData", {}).get("RaceTable", {}).get("Races", []):
        base = {
            "season": int(race["season"]),
            "round": int(race["round"]),
            "race": race.get("raceName", ""),
            "date": race.get("date", ""),
            "circuit": race.get("Circuit", {}).get("circuitId", ""),
        }
        if kind in ("results", "sprint"):
            key = "Results" if kind == "results" else "SprintResults"
            for r in race.get(key, []):
                pos_text = str(r.get("positionText", ""))
                rows.append(dict(
                    base,
                    driver=r["Driver"].get("code") or r["Driver"]["driverId"],
                    driver_id=r["Driver"]["driverId"],
                    team=r["Constructor"]["constructorId"],
                    grid=int(r.get("grid", 0) or 0),
                    finish_position=int(r["position"]) if pos_text.isdigit() else "",
                    classified=int(pos_text.isdigit()),
                    status=r.get("status", ""),
                    points=r.get("points", ""),
                ))
        elif kind == "qualifying":
            for r in race.get("QualifyingResults", []):
                rows.append(dict(
                    base,
                    driver=r["Driver"].get("code") or r["Driver"]["driverId"],
                    driver_id=r["Driver"]["driverId"],
                    team=r["Constructor"]["constructorId"],
                    quali_position=int(r["position"]),
                    q1=r.get("Q1", ""), q2=r.get("Q2", ""), q3=r.get("Q3", ""),
                ))
        else:
            raise ValueError(f"unknown kind: {kind}")
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen: dict[tuple, dict] = {}
    for r in rows:
        seen[(r["season"], r["round"], r["driver_id"])] = r
    return sorted(seen.values(), key=lambda r: (r["season"], r["round"], r["driver_id"]))


def write_rows(out_dir: Path, kind: str, rows: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / FILENAMES[kind]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS[kind])
        w.writeheader()
        w.writerows(rows)
    return path


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="") as f:
        out = []
        for r in csv.DictReader(f):
            r["season"], r["round"] = int(r["season"]), int(r["round"])
            out.append(r)
        return out
