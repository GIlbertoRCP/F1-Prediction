"""Raw material for head-to-head comparisons: per season, for every driver, their team, qualifying
position, finishing position and points in each round. The browser turns this into any pairing."""
from __future__ import annotations

from evaluation.data import Race


def build_h2h(races: list[Race]) -> dict:
    seasons: dict[int, list[Race]] = {}
    for r in races:
        seasons.setdefault(r.season, []).append(r)
    out = {}
    for season, rs in sorted(seasons.items()):
        rs = sorted(rs, key=lambda r: r.round)
        n = len(rs)
        drivers: dict[str, dict] = {}
        for i, race in enumerate(rs):
            for e in race.entries:
                d = drivers.setdefault(e.driver_id, {
                    "code": e.driver, "team": [None] * n, "q": [None] * n, "f": [None] * n, "pts": [0] * n})
                d["team"][i] = e.team
                d["q"][i] = e.quali_position
                # finishing position if classified, 0 for a retirement / not classified
                d["f"][i] = e.finish_position if (e.classified and e.finish_position) else 0
                d["pts"][i] = e.points
        out[str(season)] = {"rounds": [{"round": r.round, "race": r.name} for r in rs], "drivers": drivers}
    return out
