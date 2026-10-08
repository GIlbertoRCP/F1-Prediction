"""Backtest the production XGBRanker model: export its pre-race scores for completed races.

For every completed race of the chosen season this runs the *same* code path the dashboard uses
(f1_model.train_and_predict_for_race), but with the pickled-model cache switched off and the slow
diagnostics skipped, so each race is predicted from a model trained only on EARLIER races.
Results are appended to data/model_scores/xgb_ranker_<year>.csv and can be scored with:

    python3 -m evaluation.run --scores data/model_scores/xgb_ranker_2026.csv

Needs the project's Python environment (FastF1, XGBoost, pandas), so run it with uv:

    uv run python scripts/export_model_scores.py --rounds 2     # quick smoke test on one race
    uv run python scripts/export_model_scores.py                # all completed 2026 rounds (resumable)

The first run downloads/reads FastF1 session data and can take a long time; progress is saved after
every race, so you can stop it and re-run to continue. Re-run with --force to recompute.
"""
import argparse
import csv
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)                      # f1_model.py reads team_mappings.json / ./.f1_cache relative to cwd
sys.path.insert(0, str(ROOT))

FIELDS = ["season", "round", "race", "driver", "team", "grid_position", "rank_score",
          "predicted_position", "model_code_commit", "exported_at"]


def completed_rounds(year: int) -> set[int]:
    path = ROOT / "data" / "results" / "races.csv"
    if not path.exists():
        sys.exit("data/results/races.csv not found. Run scripts/fetch_results.py first.")
    with open(path, newline="") as f:
        return {int(r["round"]) for r in csv.DictReader(f) if int(r["season"]) == year}


def already_done(out: Path) -> set[int]:
    if not out.exists():
        return set()
    with open(out, newline="") as f:
        return {int(r["round"]) for r in csv.DictReader(f)}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, default=2026,
                    help="Season to backtest. The model's power-unit/upgrade priors are 2026-specific.")
    ap.add_argument("--rounds", type=str, default="", help="Comma-separated round numbers (default: all completed)")
    ap.add_argument("--force", action="store_true", help="Recompute rounds that are already in the CSV")
    ap.add_argument("--fresh-features", action="store_true",
                    help="Ignore the Parquet feature cache (slower; use if you suspect stale cached features)")
    args = ap.parse_args()

    try:
        import fastf1
        import f1_model
    except ImportError as e:
        sys.exit(f"Missing dependency ({e}). Run this script with the project environment: "
                 f"uv run python scripts/export_model_scores.py")

    if args.fresh_features:
        f1_model.load_parquet_cache = lambda *a, **k: None

    out = ROOT / "data" / "model_scores" / f"xgb_ranker_{args.year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    wanted = {int(x) for x in args.rounds.split(",") if x.strip()} if args.rounds else None
    done = set() if args.force else already_done(out)
    completed = completed_rounds(args.year)

    schedule = fastf1.get_event_schedule(args.year, include_testing=False)
    todo = []
    for _, ev in schedule.iterrows():
        rnd = int(ev["RoundNumber"])
        if rnd in completed and rnd not in done and (wanted is None or rnd in wanted):
            todo.append((rnd, ev["EventName"]))
    if not todo:
        print("Nothing to do: all requested completed rounds are already exported.")
        return

    commit = git_commit()
    print(f"Exporting {len(todo)} round(s) from model code {commit}: {[r for r, _ in todo]}")
    new_file = not out.exists() or args.force
    if args.force and out.exists():
        keep = []
        with open(out, newline="") as f:
            keep = [r for r in csv.DictReader(f) if int(r["round"]) not in {r_ for r_, _ in todo}]
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(keep)
        new_file = False

    failures = []
    for rnd, name in todo:
        t0 = time.time()
        print(f"\n=== Round {rnd}: {name} {args.year} ===", flush=True)
        try:
            df = f1_model.train_and_predict_for_race(args.year, name, use_cache=False, diagnostics=False)
        except Exception as e:
            print(f"!! Round {rnd} failed: {e!r}")
            failures.append((rnd, name, repr(e)))
            continue
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(out, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if new_file:
                w.writeheader()
                new_file = False
            for _, r in df.iterrows():
                w.writerow({
                    "season": args.year, "round": rnd, "race": name, "driver": r["Driver"],
                    "team": r.get("Team", ""), "grid_position": r.get("grid_position", ""),
                    "rank_score": float(r["rank_score"]), "predicted_position": int(r["predicted_position"]),
                    "model_code_commit": commit, "exported_at": now,
                })
        print(f"Round {rnd} saved ({len(df)} drivers) in {time.time() - t0:.0f}s; "
              f"predicted winner: {df.iloc[0]['Driver']}", flush=True)

    print(f"\nDone. Output: {out.relative_to(ROOT)}")
    if failures:
        print("Rounds that failed (re-run to retry):")
        for rnd, name, err in failures:
            print(f"  R{rnd} {name}: {err}")


if __name__ == "__main__":
    main()
