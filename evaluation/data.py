"""Load race results into simple objects for evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from .jolpica import read_rows


@dataclass(frozen=True)
class Entry:
    driver: str          # three-letter code
    driver_id: str       # stable id
    team: str
    grid: int            # effective starting slot (pit-lane starts go to the back)
    finish_position: int | None  # None if not classified
    classified: bool
    quali_position: int | None = None   # official qualifying classification (None if unknown)
    q_gap: float | None = None          # best qualifying lap vs the fastest in the session, in % (None if no time)
    points: float = 0.0                 # championship points scored in the race


@dataclass
class Race:
    season: int
    round: int
    name: str
    entries: list[Entry] = field(default_factory=list)
    date: str = ""   # ISO date, e.g. 2026-05-03

    @property
    def key(self) -> tuple[int, int]:
        return (self.season, self.round)

    @property
    def winner_id(self) -> str | None:
        for e in self.entries:
            if e.finish_position == 1:
                return e.driver_id
        return None


def parse_lap(text) -> float | None:
    """'1:16.732' -> 76.732 seconds; blank/garbage -> None."""
    text = str(text or "").strip()
    if not text:
        return None
    try:
        if ":" in text:
            m, s = text.split(":", 1)
            return int(m) * 60 + float(s)
        return float(text)
    except ValueError:
        return None


def load_qualifying(results_dir: Path) -> dict[tuple[int, int], dict[str, tuple[int | None, float | None]]]:
    """(season, round) -> driver_id -> (quali_position, gap % to the session's fastest lap).

    A driver's lap is their best time across Q1/Q2/Q3. Gaps are relative to the fastest
    lap set by anyone in that session, so they are comparable across circuits.
    """
    out: dict[tuple[int, int], dict[str, tuple[int | None, float | None]]] = {}
    raw: dict[tuple[int, int], list[tuple[str, int | None, float | None]]] = {}
    for r in read_rows(Path(results_dir) / "qualifying.csv"):
        laps = [t for t in (parse_lap(r.get(k)) for k in ("q1", "q2", "q3")) if t is not None]
        pos = str(r.get("quali_position", "")).strip()
        raw.setdefault((r["season"], r["round"]), []).append(
            (r["driver_id"], int(pos) if pos.isdigit() else None, min(laps) if laps else None))
    for key, rows in raw.items():
        times = [t for _, _, t in rows if t is not None]
        best = min(times) if times else None
        out[key] = {
            d: (pos, (t / best - 1.0) * 100.0 if (t is not None and best) else None)
            for d, pos, t in rows
        }
    return out


def load_races(results_dir: Path, min_entries: int = 10) -> list[Race]:
    """Races sorted chronologically. Races with no recorded winner are dropped."""
    grouped: dict[tuple[int, int], Race] = {}
    quali = load_qualifying(results_dir)
    for r in read_rows(Path(results_dir) / "races.csv"):
        key = (r["season"], r["round"])
        race = grouped.setdefault(key, Race(r["season"], r["round"], r["race"], date=r.get("date", "")))
        fin = r["finish_position"]
        qpos, qgap = quali.get(key, {}).get(r["driver_id"], (None, None))
        race.entries.append(Entry(
            driver=r["driver"], driver_id=r["driver_id"], team=r["team"],
            grid=int(r["grid"] or 0),
            finish_position=int(fin) if str(fin).strip() != "" else None,
            classified=str(r["classified"]) == "1",
            quali_position=qpos, q_gap=qgap, points=float(r.get("points") or 0),
        ))
    races = []
    for key in sorted(grouped):
        race = grouped[key]
        if len(race.entries) < min_entries or race.winner_id is None:
            continue
        n = len(race.entries)
        race.entries = [
            replace(e, grid=e.grid if e.grid > 0 else n + 1)
            for e in race.entries
        ]
        races.append(race)
    return races


def coverage(races: list[Race]) -> dict[int, tuple[int, list[int]]]:
    """Per season: (races present, missing round numbers up to the highest round seen)."""
    by_season: dict[int, set[int]] = {}
    for r in races:
        by_season.setdefault(r.season, set()).add(r.round)
    return {
        s: (len(rounds), [x for x in range(1, max(rounds) + 1) if x not in rounds])
        for s, rounds in sorted(by_season.items())
    }
