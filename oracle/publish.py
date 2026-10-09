"""Update the Oracle: backfill the backtest, freeze a live forecast for the upcoming race,
and write the JSON the front page reads.

    python3 -m oracle.publish                 # normal run after fetching fresh results
    python3 -m oracle.publish --rebuild-backtest
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from evaluation.data import load_races
from . import engine, store
from .schedule import read_schedule
from .service import BACKTEST_FILE, LIVE_FILE, build_bundle

ROOT = Path(__file__).resolve().parent.parent


def backfill_backtest(races, pred_dir: Path, force: bool = False) -> int:
    """Replay history: forecast every race from the 16th onward using only earlier races."""
    path = pred_dir / BACKTEST_FILE
    existing = {(r["season"], r["round"]): r for r in store.read_log(path)}
    version = engine.model_version()
    if not force and existing and all(r["model_version"] == version for r in existing.values()):
        missing = [r for r in races[engine.MIN_TRAIN:] if r.key not in existing]
    else:
        existing, missing = {}, list(races[engine.MIN_TRAIN:])
    if not missing:
        return 0
    todo = {r.key for r in missing}
    for i, race in enumerate(races):
        if race.key not in todo:
            continue
        probs = engine.forecast(races[:i], race)
        existing[race.key] = {
            "season": race.season, "round": race.round, "race": race.name, "date": race.date,
            "kind": "backtest", "model": engine.MODEL_NAME, "model_version": version,
            "made_at": None, "grid_source": "race_grid", "train_races": i,
            "predictions": engine.entries_payload(race, probs),
        }
    store.write_backtest(path, [existing[k] for k in sorted(existing)])
    return len(missing)


def freeze_live(races, results_dir: Path, pred_dir: Path, now: dt.datetime) -> list[str]:
    """Log a forecast for every upcoming race that has a grid but no result. Never overwrites."""
    messages = []
    schedule = {(r["season"], r["round"]): r for r in read_schedule(results_dir / "schedule.csv")}
    for race in engine.load_pending(results_dir, races):
        label = f"{race.season} R{race.round} {race.name}"
        sched = schedule.get(race.key)
        start = race.date
        if sched and sched.get("time"):
            start_dt = dt.datetime.fromisoformat(f"{sched['date']}T{sched['time'].rstrip('Z')}+00:00")
            too_late = now >= start_dt
        else:
            too_late = bool(start) and now.date().isoformat() > start
        if too_late:
            messages.append(f"SKIPPED {label}: race has started; refusing to log a forecast after the fact "
                            "(refresh results with scripts/fetch_results.py)")
            continue
        probs = engine.forecast(races, race)
        record = {
            "season": race.season, "round": race.round, "race": race.name, "date": race.date,
            "kind": "live", "model": engine.MODEL_NAME, "model_version": engine.model_version(),
            "made_at": now.isoformat(timespec="seconds"), "grid_source": "qualifying",
            "train_races": len(races), "predictions": engine.entries_payload(race, probs),
        }
        added = store.append_live(pred_dir / LIVE_FILE, record)
        messages.append(f"{'FROZE' if added else 'kept existing'} forecast for {label}")
    return messages


def write_site_data(bundle: dict, out_dir: Path) -> None:
    data = out_dir / "data"
    (data / "races").mkdir(parents=True, exist_ok=True)
    for name in ("meta", "forecast", "track_record"):
        (data / f"{name}.json").write_text(json.dumps(bundle[name], indent=1))
    for key, page in bundle["races"].items():
        (data / "races" / f"{key}.json").write_text(json.dumps(page))
    index = sorted(({"key": k, "season": p["season"], "round": p["round"], "race": p["race"],
                     "date": p["date"], "kind": p["kind"]} for k, p in bundle["races"].items()),
                   key=lambda r: (r["season"], r["round"]), reverse=True)
    (data / "races.json").write_text(json.dumps(index))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(ROOT / "data" / "results"))
    ap.add_argument("--predictions-dir", default=str(ROOT / "data" / "predictions"))
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--rebuild-backtest", action="store_true")
    args = ap.parse_args(argv)
    results_dir, pred_dir, out = Path(args.results_dir), Path(args.predictions_dir), Path(args.out)

    races = load_races(results_dir)
    now = dt.datetime.now(dt.timezone.utc)
    n = backfill_backtest(races, pred_dir, force=args.rebuild_backtest)
    print(f"backtest: {n} forecasts (re)computed")
    for msg in freeze_live(races, results_dir, pred_dir, now):
        print(msg)
    bundle = build_bundle(results_dir, pred_dir, now)
    write_site_data(bundle, out)
    ok = bundle["meta"]["live_log"]
    print(f"live log: {ok['detail']}")
    print(f"site data written to {out}/data")
    return 0 if ok["chain_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
