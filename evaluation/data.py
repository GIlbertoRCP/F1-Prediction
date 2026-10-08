"""Load race results into simple objects for evaluation."""
from __future__ import annotations

from dataclasses import dataclass, field
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


def load_races(results_dir: Path, min_entries: int = 10) -> list[Race]:
    """Races sorted chronologically. Races with no recorded winner are dropped."""
    grouped: dict[tuple[int, int], Race] = {}
    for r in read_rows(Path(results_dir) / "races.csv"):
        key = (r["season"], r["round"])
        race = grouped.setdefault(key, Race(r["season"], r["round"], r["race"], date=r.get("date", "")))
        fin = r["finish_position"]
        race.entries.append(Entry(
            driver=r["driver"], driver_id=r["driver_id"], team=r["team"],
            grid=int(r["grid"] or 0),
            finish_position=int(fin) if str(fin).strip() != "" else None,
            classified=str(r["classified"]) == "1",
        ))
    races = []
    for key in sorted(grouped):
        race = grouped[key]
        if len(race.entries) < min_entries or race.winner_id is None:
            continue
        n = len(race.entries)
        race.entries = [
            Entry(e.driver, e.driver_id, e.team, e.grid if e.grid > 0 else n + 1,
                  e.finish_position, e.classified)
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
