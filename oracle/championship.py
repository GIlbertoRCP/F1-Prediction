"""Championship outlook for the site: title odds from the season simulation, a replay of how those odds
moved over the current season, and a hash-chained log of the forecasts made live."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from evaluation.season import (MIN_TRAIN, TAU, fit_form_model, forecast_season, load_sprint_points,
                               simulate_season, standing_after)

from . import store
from .schedule import read_schedule

LIVE_FILE = "championship_live.jsonl"
N_SIMS = 10000
REPLAY_SIMS = 2000
FIRST_CUTOFF = 3


def remaining_calendar(races, sprints, schedule, season: int, after: int) -> list[dict]:
    """Rounds of `season` after `after`: completed rounds known from the results (sprint flag from the sprint
    results) plus the not-yet-run rounds from the calendar."""
    sprint_rounds = {rnd for (s, rnd, _d) in sprints if s == season}
    out = {}
    for r in races:
        if r.season == season and r.round > after:
            out[r.round] = {"round": r.round, "race": r.name, "date": r.date, "sprint": r.round in sprint_rounds}
    played = {r.round for r in races if r.season == season}
    for row in schedule:
        if row["season"] == season and row["round"] > after and row["round"] not in played:
            out[row["round"]] = {"round": row["round"], "race": row["race"], "date": row["date"],
                                 "sprint": row.get("sprint") == "1"}
    return [out[k] for k in sorted(out)]


def _round(x: float, nd: int = 4) -> float:
    return round(x, nd)


def _public(fc: dict) -> dict:
    keep = lambda rows, extra: [  # noqa: E731
        {**{k: (_round(r[k]) if k == "title" else (round(r[k], 1) if isinstance(r[k], float) else r[k]))
            for k in extra}} for r in rows]
    return {
        "season": fc["season"], "after_round": fc["after_round"], "n_sims": fc["n_sims"], "tau": fc["tau"],
        "remaining": fc["remaining"],
        "drivers": keep([d for d in fc["drivers"] if d["racing"] or d["points"] > 0],
                        ["id", "code", "team", "points", "title", "mean", "p10", "p50", "p90", "racing"]),
        "teams": keep(fc["teams"], ["team", "points", "title", "mean", "p10", "p50", "p90"]),
    }


def current_outlook(races, sprints, schedule, season: int, after: int, n_sims: int = N_SIMS) -> dict | None:
    remaining = remaining_calendar(races, sprints, schedule, season, after)
    if len(races) < MIN_TRAIN:
        return None
    fc = forecast_season(races, sprints, season, after, remaining, n_sims=n_sims)
    return _public(fc)


def replay(races, sprints, schedule, season: int, top: int = 6) -> dict:
    """How the title odds would have moved over `season`, each point computed from results up to that round only.
    A replay (labelled as such on the site), not the live log."""
    rounds = sorted(r.round for r in races if r.season == season)
    out = []
    for cutoff in rounds:
        if cutoff < FIRST_CUTOFF:
            continue
        remaining = remaining_calendar(races, sprints, schedule, season, cutoff)
        if not remaining:
            continue
        fc = forecast_season(races, sprints, season, cutoff, remaining, n_sims=REPLAY_SIMS, seed=cutoff)
        out.append({"after": cutoff, "drivers": [
            {"code": d["code"], "team": d["team"], "title": _round(d["title"]), "now": d["points"],
             "mean": round(d["mean"], 1)}
            for d in fc["drivers"][:top]]})
    return {"total_rounds": max([r["round"] for r in remaining_calendar(races, sprints, schedule, season, 0)] or [0]),
            "cutoffs": out}


def freeze_live(races, sprints, schedule, pred_dir: Path, now: dt.datetime, season: int, after: int) -> str | None:
    """Log the title odds after round `after`, once, and only before the next race has started."""
    remaining = remaining_calendar(races, sprints, schedule, season, after)
    if not remaining:
        return None
    nxt = remaining[0]
    start = nxt["date"]
    if start and now.date().isoformat() > start:
        return f"SKIPPED championship forecast after R{after}: R{nxt['round']} has already been run"
    fc = _public(forecast_season(races, sprints, season, after, remaining, n_sims=N_SIMS))
    import hashlib
    from evaluation import season as season_mod
    version = hashlib.sha256(Path(season_mod.__file__).read_bytes()).hexdigest()[:10]
    record = {"season": season, "round": after, "kind": "live", "made_at": now.isoformat(timespec="seconds"),
              "model": "form_points_pl", "model_version": version, "outlook": fc}
    added = store.append_live(pred_dir / LIVE_FILE, record)
    return f"{'FROZE' if added else 'kept existing'} championship forecast after {season} R{after}"


def live_summary(pred_dir: Path) -> dict:
    records = store.read_log(pred_dir / LIVE_FILE)
    ok, msg = store.verify_chain(records)
    return {"records": len(records), "chain_ok": ok, "detail": msg,
            "log": [{"season": r["season"], "after_round": r["round"], "made_at": r["made_at"], "hash": r["hash"],
                     "leader": max(r["outlook"]["drivers"], key=lambda d: d["title"])["code"],
                     "leader_title": max(d["title"] for d in r["outlook"]["drivers"])} for r in records]}


def build(races, results_dir: Path, pred_dir: Path, history_path: Path, now: dt.datetime, with_replay: bool = True) -> dict:
    sprints = load_sprint_points(results_dir)
    schedule = read_schedule(results_dir / "schedule.csv")
    last = races[-1]
    season, after = last.season, last.round
    out = {"status": "none", "backtest": None}
    if history_path.exists():
        out["backtest"] = json.loads(history_path.read_text())
    remaining = remaining_calendar(races, sprints, schedule, season, after)
    if not remaining:
        out["status"] = "final" if len([r for r in races if r.season == season]) else "none"
    else:
        out["status"] = "open"
        out["current"] = current_outlook(races, sprints, schedule, season, after)
        out["tau"] = TAU
        if with_replay:
            out["replay"] = replay(races, sprints, schedule, season)
    out["live"] = live_summary(pred_dir)
    return out
