"""Run the walk-forward baseline evaluation and write a Markdown report.

    python3 -m evaluation.run                       # data/results -> reports/baselines.md
    python3 -m evaluation.run --min-train 30
    python3 -m evaluation.run --predictions my_model.csv   # score a model that outputs win probabilities
    python3 -m evaluation.run --scores data/model_scores/xgb_ranker_2026.csv   # score a ranker's raw scores

--predictions CSV columns: season, round, driver_id (or driver), win_prob.
Probabilities are floored at 0.001 and re-normalised per race so a model is not
punished infinitely for a single confident miss.

--scores CSV columns: season, round, driver (3-letter code) or driver_id, rank_score (higher = better).
Scores are mapped to win probabilities walk-forward (see evaluation/ranker.py), alone and stacked
on the grid+form baseline. A second table covers only races on/after --freeze-date, i.e. races the
model's hand-set constants could not have been tuned on.
"""
from __future__ import annotations

import argparse
import csv
import datetime
from pathlib import Path

from .data import coverage, load_races
from .metrics import calibration_table, paired_diff_ci, score_race, summarize
from .models import build_feature_table, default_models
from .ranker import RankerModel
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


def load_scores(path: Path, races):
    """Read a ranker's scores -> ({race_key: {driver_id: score}}, [warnings])."""
    by_code = {(r.key, e.driver): e.driver_id for r in races for e in r.entries}
    known_keys = {r.key for r in races}
    scores: dict[tuple, dict] = {}
    unmatched: list[str] = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (int(row["season"]), int(row["round"]))
            if key not in known_keys:
                continue
            did = row.get("driver_id") or by_code.get((key, row.get("driver", "")))
            if not did:
                unmatched.append(f"{key[0]} R{key[1]} {row.get('driver', '?')}")
                continue
            scores[key] = scores.get(key, {})
            scores[key][did] = float(row.get("rank_score", row.get("score")))
    warnings = []
    if unmatched:
        warnings.append(f"{len(unmatched)} scored driver(s) could not be matched to results and were ignored: "
                        + ", ".join(unmatched[:8]) + (" ..." if len(unmatched) > 8 else ""))
    return scores, warnings


def evaluate_scored(races, table, scores, min_scored: int):
    """Walk-forward over races that have scores; baselines are evaluated on exactly the same races."""
    idx_of = {r.key: i for i, r in enumerate(races)}
    scored_idx = sorted(idx_of[k] for k in scores if k in idx_of)
    eval_idx = scored_idx[min_scored:]
    models = default_models() + [
        RankerModel("ranker_only", scores),
        RankerModel("grid_form_plus_ranker", scores, stack_on_baseline=True),
    ]
    results = {m.name: [] for m in models}
    betas = {}
    for t in eval_idx:
        race = races[t]
        for m in models:
            m.fit(races[:t], table[:t])
            results[m.name].append(score_race(race.key, m.predict(race, table[t]), race.winner_id))
            if isinstance(m, RankerModel):
                betas[m.name] = (m.beta, m.n_train)
    return results, betas


def ranker_section(title, results, betas, seed, note="") -> str:
    n = len(next(iter(results.values()))) if results else 0
    out = [f"### {title} ({n} races)\n"]
    if note:
        out.append(note + "\n")
    if n == 0:
        out.append("_No races in this subset._\n")
        return "\n".join(out)
    out.append("| Model | Winner = top pick | Winner in top 3 | Winner's avg rank | Log loss ↓ | Brier ↓ |")
    out.append("|---|---|---|---|---|---|")
    for name, sc in results.items():
        s = summarize(sc, seed)
        out.append(f"| `{name}` | {fmt_ci(s['top1'], pct=True)} | {fmt_ci(s['top3'], pct=True)} | "
                   f"{fmt_ci(s['mean_rank'], nd=2)} | {fmt_ci(s['logloss'])} | {fmt_ci(s['brier'])} |")
    out.append("")
    for ref in ("grid_prior", "grid_plus_form"):
        out.append(f"Paired log-loss difference vs `{ref}` (negative = better):")
        for name in ("ranker_only", "grid_form_plus_ranker"):
            d, (lo, hi) = paired_diff_ci([x.logloss for x in results[name]],
                                         [x.logloss for x in results[ref]], seed=seed)
            verdict = "better" if hi < 0 else ("worse" if lo > 0 else "not distinguishable")
            out.append(f"- `{name}`: {d:+.3f} [{lo:+.3f}, {hi:+.3f}] → **{verdict}**")
        out.append("")
    if betas:
        out.append("Fitted weight on the ranker score at the last race (0 = ignored; larger = trusted more): "
                   + ", ".join(f"`{k}` β={b:.2f} (from {n_tr} earlier scored races)" for k, (b, n_tr) in betas.items()) + "\n")
    return "\n".join(out)


def build_ranker_report(races, table, scores, warnings, min_scored, freeze_date, seed) -> str:
    results, betas = evaluate_scored(races, table, scores, min_scored)
    date_of = {r.key: r.date for r in races}
    out = ["\n## Your ranker vs the baselines\n"]
    out.append(f"Scores exist for {len(scores)} races; the first {min_scored} are used only to fit the score→probability "
               f"mapping, the rest are evaluated. Every row below is scored on the **same races**. "
               f"Treat conclusions as provisional: samples this small give wide intervals.\n")
    for w in warnings:
        out.append(f"> **Warning:** {w}\n")
    out.append(ranker_section("All evaluated scored races", results, betas, seed,
                              "These races were available to the author while the model's hand-set constants "
                              "(power-unit ratings, upgrade scores, grid-anchor weight) were chosen, so they may be flattering."))
    if freeze_date:
        hold = {name: [x for x in sc if date_of.get(x.key, "") >= freeze_date] for name, sc in results.items()}
        out.append(ranker_section(f"Clean holdout: races on/after {freeze_date}", hold, betas, seed,
                                  f"Races after the model code was last edited ({freeze_date}), so nothing was tuned on them. "
                                  f"This is the fairest test of the model as it stands."))
    return "\n".join(out)


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
    ap.add_argument("--scores", type=Path, help="CSV of a ranker's raw scores (see scripts/export_model_scores.py)")
    ap.add_argument("--min-scored", type=int, default=4,
                    help="Scored races used only to fit the score->probability mapping before evaluating")
    ap.add_argument("--freeze-date", default="2026-06-17",
                    help="Date the model's hand-set constants were last edited; races on/after it form the clean holdout")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "baselines.md")
    args = ap.parse_args()

    races = load_races(args.results_dir)
    for flag, path, hint in (
        ("--scores", args.scores, "Create it first with: uv run python scripts/export_model_scores.py"),
        ("--predictions", args.predictions, ""),
    ):
        if path and not path.exists():
            raise SystemExit(f"{flag} file not found: {path}. {hint}".strip())
    if len(races) <= args.min_train + 5:
        raise SystemExit(f"Only {len(races)} races found in {args.results_dir}; need more than {args.min_train + 5}.")
    external = load_external(args.predictions, races) if args.predictions else None
    results = walk_forward(races, default_models(), args.min_train, build_feature_table(races), external)
    report = build_report(races, results, args.min_train, args.seed)
    if args.scores:
        scores, warns = load_scores(args.scores, races)
        if len(scores) <= args.min_scored + 1:
            raise SystemExit(f"Only {len(scores)} scored race(s) matched the results; need more than {args.min_scored + 1}.")
        report += build_ranker_report(races, build_feature_table(races), scores, warns,
                                      args.min_scored, args.freeze_date, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report)
    print(report)
    print(f"(saved to {args.out})")


if __name__ == "__main__":
    main()
