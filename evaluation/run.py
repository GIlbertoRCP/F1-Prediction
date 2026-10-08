"""Run the walk-forward baseline evaluation and write a Markdown report.

    python3 -m evaluation.run                       # data/results -> reports/baselines.md
    python3 -m evaluation.run --min-train 30
    python3 -m evaluation.run --predictions my_model.csv   # also score your own model

--predictions CSV columns: season, round, driver_id (or driver), win_prob.
Probabilities are floored at 0.001 and re-normalised per race so a model is not
punished infinitely for a single confident miss.
"""
from __future__ import annotations

import argparse
import csv
import datetime
from pathlib import Path

from .data import coverage, load_races
from .metrics import calibration_table, paired_diff_ci, summarize
from .models import build_feature_table, default_models
from .walkforward import walk_forward

ROOT = Path(__file__).resolve().parent.parent
REFERENCE = "grid_prior"


def load_external(path: Path, races) -> dict:
    codes = {(r.key, e.driver): e.driver_id for r in races for e in r.entries}
    by_race: dict[tuple, dict] = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (int(row["season"]), int(row["round"]))
            did = row.get("driver_id") or codes.get((key, row.get("driver", "")))
            if did:
                by_race.setdefault(key, {})[did] = float(row["win_prob"])
    for key, probs in by_race.items():
        probs = {d: max(p, 0.001) for d, p in probs.items()}
        z = sum(probs.values())
        by_race[key] = {d: p / z for d, p in probs.items()}
    return {path.stem: by_race}


def fmt_ci(v, pct=False, nd=3):
    mean, (lo, hi) = v
    if pct:
        return f"{mean*100:.1f}% [{lo*100:.0f}–{hi*100:.0f}]"
    return f"{mean:.{nd}f} [{lo:.{nd}f}–{hi:.{nd}f}]"


def build_report(races, results, min_train, seed) -> str:
    n_eval = len(next(iter(results.values())))
    first, last = races[min_train], races[-1]
    out = []
    out.append("# Baseline evaluation: who wins the race?\n")
    out.append(f"_Generated {datetime.date.today().isoformat()} by `python3 -m evaluation.run`. "
               f"Walk-forward: each race is predicted using only earlier races._\n")
    out.append("## Data\n")
    out.append(f"- {len(races)} race weekends loaded; **{n_eval} evaluated** "
               f"({first.season} R{first.round} → {last.season} R{last.round}); the first {min_train} are training warm-up.")
    cov = coverage(races)
    for s, (n, missing) in cov.items():
        gap = f", missing rounds {missing}" if missing else ""
        out.append(f"- {s}: {n} races{gap}")
    gaps = any(m for _, m in cov.values())
    if gaps:
        out.append("\n> **Caution:** the dataset has gaps, so 'recent form' skips races and the "
                   "numbers below are indicative only. Run `python3 scripts/fetch_results.py` "
                   "to download complete history, then re-run.\n")
    out.append("\n## Results (95% bootstrap CI over races in brackets)\n")
    out.append("| Model | Winner = top pick | Winner in top 3 | Winner's avg rank | Log loss ↓ | Brier ↓ |")
    out.append("|---|---|---|---|---|---|")
    summ = {name: summarize(sc, seed) for name, sc in results.items()}
    for name, s in summ.items():
        out.append(f"| `{name}` | {fmt_ci(s['top1'], pct=True)} | {fmt_ci(s['top3'], pct=True)} | "
                   f"{fmt_ci(s['mean_rank'], nd=2)} | {fmt_ci(s['logloss'])} | {fmt_ci(s['brier'])} |")
    out.append("\n`grid_prior` always picks the pole sitter, so its 'top pick' rate is the "
               "**'pole sitter wins' baseline**. Log loss of `uniform` is ln(≈20) ≈ 3.0; lower is better.\n")
    if REFERENCE in results:
        out.append(f"## Paired difference in log loss vs `{REFERENCE}` (negative = better)\n")
        ref = [s.logloss for s in results[REFERENCE]]
        for name, sc in results.items():
            if name == REFERENCE:
                continue
            d, (lo, hi) = paired_diff_ci([s.logloss for s in sc], ref, seed=seed)
            verdict = "better" if hi < 0 else ("worse" if lo > 0 else "not distinguishable")
            out.append(f"- `{name}`: {d:+.3f} [{lo:+.3f}, {hi:+.3f}] → **{verdict}**")
        out.append("")
    best = min(summ, key=lambda n: summ[n]["logloss"][0])
    out.append(f"## Calibration of `{best}` (pooled over all drivers)\n")
    out.append("| Predicted bucket | Driver-races | Mean predicted | Observed win rate |")
    out.append("|---|---|---|---|")
    for lo, hi, n, mp, obs in calibration_table(results[best]):
        out.append(f"| {lo*100:.0f}–{hi*100:.0f}% | {n} | {mp*100:.1f}% | {obs*100:.1f}% |")
    out.append("\nA well-calibrated model has 'predicted' ≈ 'observed' in every bucket. "
               "Small samples make rare buckets noisy.\n")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", type=Path, default=ROOT / "data" / "results")
    ap.add_argument("--min-train", type=int, default=15)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--predictions", type=Path, help="CSV of your own model's win probabilities")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "baselines.md")
    args = ap.parse_args()

    races = load_races(args.results_dir)
    if len(races) <= args.min_train + 5:
        raise SystemExit(f"Only {len(races)} races found in {args.results_dir}; need more than {args.min_train + 5}.")
    external = load_external(args.predictions, races) if args.predictions else None
    results = walk_forward(races, default_models(), args.min_train, build_feature_table(races), external)
    report = build_report(races, results, args.min_train, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)
    print(report)
    print(f"(saved to {args.out})")


if __name__ == "__main__":
    main()
