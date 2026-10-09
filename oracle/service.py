"""Builds everything the front page and API serve, from the results data and the prediction logs."""
from __future__ import annotations

import datetime as dt
import math
from collections import defaultdict
from pathlib import Path

from evaluation.data import Race, load_races
from evaluation.models import GridPrior
from evaluation.metrics import bootstrap_ci, calibration_table, mean, score_race
from . import engine, store
from .schedule import next_race, read_schedule

LIVE_FILE = "live.jsonl"
BACKTEST_FILE = "backtest.jsonl"


def _ci(values: list[float]) -> dict:
    lo, hi = bootstrap_ci(values)
    return {"mean": mean(values), "lo": lo, "hi": hi}


def settle(records: list[dict], by_key: dict[tuple[int, int], Race]) -> list[dict]:
    """Join forecasts with results. Returns one row per forecast whose race has finished."""
    rows = []
    for rec in records:
        key = (rec["season"], rec["round"])
        race = by_key.get(key)
        if race is None or race.winner_id is None:
            continue
        probs = {p["driver_id"]: p["p"] for p in rec["predictions"]}
        if race.winner_id not in probs:
            continue
        sc = score_race(key, probs, race.winner_id)
        ids = {e.driver_id: e for e in race.entries}
        pick = max(probs, key=lambda d: (probs[d], d))
        pole = min(race.entries, key=lambda e: (e.grid, e.driver_id))
        rows.append({
            "season": key[0], "round": key[1], "race": race.name, "date": race.date,
            "kind": rec["kind"], "pick": ids[pick].driver if pick in ids else pick,
            "pick_p": probs[pick], "winner": ids[race.winner_id].driver, "winner_id": race.winner_id,
            "p_winner": sc.p_winner, "rank": sc.rank, "hit": sc.top1, "top3": sc.top3,
            "logloss": sc.logloss, "brier": sc.brier, "pole_hit": pole.driver_id == race.winner_id,
            "_score": sc,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"n": 0}
    n = len(rows)
    uni = mean(math.log(len(r["_score"].pairs)) for r in rows)
    return {
        "n": n,
        "top1": _ci([1.0 if r["hit"] else 0.0 for r in rows]),
        "top3": _ci([1.0 if r["top3"] else 0.0 for r in rows]),
        "logloss": _ci([r["logloss"] for r in rows]),
        "brier": _ci([r["brier"] for r in rows]),
        "avg_winner_prob": mean(r["p_winner"] for r in rows),
        "pole_top1": mean(1.0 if r["pole_hit"] else 0.0 for r in rows),
        "uniform_logloss": uni,
    }


def slot_prior_logloss(races: list[Race], keys: set[tuple[int, int]]) -> float:
    """Mean log loss of 'chance depends only on starting slot', replayed on the same races."""
    losses = []
    for i, race in enumerate(races):
        if race.key in keys:
            probs = GridPrior().fit(races[:i], None).predict(race, None)
            losses.append(score_race(race.key, probs, race.winner_id).logloss)
    return mean(losses)


def _public(row: dict) -> dict:
    return {k: v for k, v in row.items() if not k.startswith("_")}


def build_bundle(results_dir: Path, pred_dir: Path, now: dt.datetime | None = None) -> dict:
    """Return {"meta", "forecast", "track_record", "races": {"2024-5": {...}}}."""
    now = now or dt.datetime.now(dt.timezone.utc)
    results_dir, pred_dir = Path(results_dir), Path(pred_dir)
    races = load_races(results_dir)
    by_key = {r.key: r for r in races}
    live = store.read_log(pred_dir / LIVE_FILE)
    backtest = store.read_log(pred_dir / BACKTEST_FILE)
    chain_ok, chain_msg = store.verify_chain(live)

    live_rows = settle(live, by_key)
    bt_rows = settle(backtest, by_key)
    live_keys = {(r["season"], r["round"]) for r in live_rows}
    all_rows = sorted(live_rows + [r for r in bt_rows if (r["season"], r["round"]) not in live_keys],
                      key=lambda r: (r["season"], r["round"]))

    # per-season backtest summary
    seasons = defaultdict(list)
    for r in bt_rows:
        seasons[r["season"]].append(r)
    cal = [{"lo": lo, "hi": hi, "n": n, "predicted": pr, "observed": ob}
           for lo, hi, n, pr, ob in (calibration_table([r["_score"] for r in bt_rows]) if bt_rows else [])]

    # current forecast: the newest live record whose race has no result yet
    schedule = read_schedule(results_dir / "schedule.csv")
    today = now.date().isoformat()
    pending = [r for r in live if (r["season"], r["round"]) not in by_key]
    forecast = {"status": "none", "next_race": next_race(schedule, today)}
    if pending:
        rec = max(pending, key=lambda r: (r["season"], r["round"]))
        forecast = {"status": "open", "race": {k: rec[k] for k in ("season", "round", "race", "date")},
                    "made_at": rec["made_at"], "grid_source": rec["grid_source"],
                    "model": rec["model"], "model_version": rec["model_version"],
                    "hash": rec["hash"], "predictions": rec["predictions"],
                    "next_race": next_race(schedule, today)}
    latest = all_rows[-1] if all_rows else None

    # per-race detail (live record wins over the backtest record for the same race)
    records = {(r["season"], r["round"]): r for r in backtest}
    records.update({(r["season"], r["round"]): r for r in live})
    race_pages = {}
    for key, rec in records.items():
        race = by_key.get(key)
        result = None
        if race:
            fin = sorted((e for e in race.entries if e.finish_position),
                         key=lambda e: e.finish_position)[:10]
            result = {"winner_id": race.winner_id,
                      "finishers": [{"pos": e.finish_position, "driver": e.driver, "team": e.team,
                                     "grid": e.grid} for e in fin]}
        race_pages[f"{key[0]}-{key[1]}"] = {
            "season": key[0], "round": key[1], "race": rec["race"], "date": rec["date"],
            "kind": rec["kind"], "made_at": rec.get("made_at"), "grid_source": rec["grid_source"],
            "predictions": rec["predictions"], "result": result,
        }

    return {
        "meta": {
            "generated_at": now.isoformat(timespec="seconds"),
            "model": engine.MODEL_NAME, "model_version": engine.model_version(),
            "data_through": {"season": races[-1].season, "round": races[-1].round,
                             "race": races[-1].name, "date": races[-1].date} if races else None,
            "live_log": {"records": len(live), "chain_ok": chain_ok, "detail": chain_msg},
        },
        "forecast": forecast,
        "track_record": {
            "live": summarize(live_rows),
            "backtest": summarize(bt_rows),
            "by_season": {str(s): summarize(rs) for s, rs in sorted(seasons.items())},
            "calibration": cal,
            "reference": ({"slot_prior_logloss": slot_prior_logloss(
                races, {(r["season"], r["round"]) for r in bt_rows})} if bt_rows else None),
            "latest": _public(latest) if latest else None,
            "races": [_public(r) for r in all_rows],
        },
        "races": race_pages,
    }
