"""The fair telemetry test.

Question: do practice-session pace features (known before qualifying) improve winner probabilities,
and how good can a forecast be *before* the grid is set?

Fairness rules:
  * Every model is scored on exactly the same races (those after a warm-up inside the practice-data era).
  * Form features come from the full history, so nobody loses the pre-practice-era races as context.
  * The practice models can only train on races that have practice data, so the control model
    (`grid_plus_form_tele`) is trained on that same window; `grid_plus_form_all` shows the effect of
    having more training history.
  * Walk-forward: a race is predicted only from earlier races.

    python3 -m evaluation.telemetry_eval --out reports/telemetry.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .data import load_races
from .metrics import bootstrap_ci, calibration_table, mean, paired_diff_ci, score_race
from .models import BASE_FEATURES, ConditionalLogit, build_feature_table

FORM = ["team_score", "driver_score", "driver_win", "team_win"]
FP4 = ["fp_gap", "team_fp_gap", "fp_long", "team_fp_long"]
FP6 = FP4 + ["driver_fp_form", "team_fp_form"]

# name, features, trains on: "all" history or only the practice-data window
SPECS = [
    ("grid_plus_form_all", BASE_FEATURES, "all"),
    ("grid_plus_form_tele", BASE_FEATURES, "tele"),
    ("grid_form_fp", BASE_FEATURES + FP4, "tele"),
    ("grid_form_fp_form", BASE_FEATURES + FP6, "tele"),
    ("pre_form_only", FORM, "tele"),
    ("pre_quali_fp", FORM + FP4, "tele"),
    ("pre_quali_fp_form", FORM + FP6, "tele"),
]
REFERENCE = "grid_plus_form_all"
CONTROL = "grid_plus_form_tele"


def run(races, min_train: int, min_coverage: float = 0.8):
    table = build_feature_table(races)
    has = [any(e.fp_gap is not None for e in r.entries) for r in races]
    first = next((i for i, h in enumerate(has) if h), None)
    if first is None:
        return None
    covered = sum(has[first:]) / len(has[first:])
    scores = {name: [] for name, _, _ in SPECS}
    used = []
    for t in range(first + min_train, len(races)):
        if not has[t]:
            continue                       # score only weekends with practice data
        used.append(races[t])
        for name, feats, window in SPECS:
            start = 0 if window == "all" else first
            m = ConditionalLogit(name, feats).fit(races[start:t], table[start:t])
            scores[name].append(score_race(races[t].key, m.predict(races[t], table[t]), races[t].winner_id))
    return {"scores": scores, "races": used, "first": races[first], "coverage": covered, "n_has": sum(has)}


def fmt(vals, pct=False):
    m, (lo, hi) = mean(vals), bootstrap_ci(vals)
    return f"{m*100:.1f}% [{lo*100:.0f}–{hi*100:.0f}]" if pct else f"{m:.3f} [{lo:.3f}, {hi:.3f}]"


def report(res, min_train):
    sc = res["scores"]
    n = len(res["races"])
    out = ["# Practice pace: does it help?\n",
           f"_Walk-forward. Practice data starts at {res['first'].season} R{res['first'].round}; {res['n_has']} weekends have it "
           f"({res['coverage']*100:.0f}% of the era). Warm-up: {min_train} weekends. **{n} races scored**, identical for every model "
           f"({res['races'][0].season} R{res['races'][0].round} to {res['races'][-1].season} R{res['races'][-1].round})._\n",
           "## Results\n",
           "| Model | Uses the grid? | Winner = top pick | Winner in top 3 | Log loss ↓ |",
           "|---|---|---|---|---|"]
    for name, feats, _ in SPECS:
        uses = "yes" if "log_grid" in feats else "no"
        s = sc[name]
        out.append(f"| `{name}` | {uses} | {fmt([1.0 if x.top1 else 0.0 for x in s], True)} | "
                   f"{fmt([1.0 if x.top3 else 0.0 for x in s], True)} | {fmt([x.logloss for x in s])} |")
    out.append("")
    for ref, label in ((CONTROL, "the same model without practice data, trained on the same window"),
                       (REFERENCE, "the production model (all history)")):
        out.append(f"## Paired log-loss difference vs `{ref}` ({label}); negative = better\n")
        base = [x.logloss for x in sc[ref]]
        for name, feats, _ in SPECS:
            if name == ref or ("log_grid" not in feats and ref == CONTROL):
                continue
            d, (lo, hi) = paired_diff_ci([x.logloss for x in sc[name]], base)
            verdict = "better" if hi < 0 else ("worse" if lo > 0 else "not distinguishable")
            out.append(f"- `{name}`: {d:+.3f} [{lo:+.3f}, {hi:+.3f}] → **{verdict}**")
        out.append("")
    out.append("## Before qualifying: how much does practice pace buy?\n")
    base = [x.logloss for x in sc["pre_form_only"]]
    for name in ("pre_quali_fp", "pre_quali_fp_form"):
        d, (lo, hi) = paired_diff_ci([x.logloss for x in sc[name]], base)
        verdict = "better" if hi < 0 else ("worse" if lo > 0 else "not distinguishable")
        out.append(f"- `{name}` vs `pre_form_only` (same inputs minus practice pace): {d:+.3f} [{lo:+.3f}, {hi:+.3f}] → **{verdict}**")
    gap = mean(x.logloss for x in sc["pre_quali_fp"]) - mean(x.logloss for x in sc[CONTROL])
    out.append(f"\nFor scale: a forecast made after qualifying (`{CONTROL}`) scores {gap:+.3f} log loss better than the best pre-qualifying model "
               "(negative means the pre-qualifying model is ahead).\n")
    best = min(("pre_quali_fp", "pre_quali_fp_form"), key=lambda n: mean(x.logloss for x in sc[n]))
    out.append(f"### Calibration of `{best}` (pre-qualifying)\n")
    out.append("| Predicted bucket | Driver-races | Mean predicted | Observed |\n|---|---|---|---|")
    for lo_, hi_, k, pr, ob in calibration_table(sc[best]):
        out.append(f"| {lo_*100:.0f}–{hi_*100:.0f}% | {k} | {pr*100:.1f}% | {ob*100:.1f}% |")
    out.append("\nSeven models were compared on the same races, so the best-looking one is mildly flattered by selection.\n")
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="data/results")
    ap.add_argument("--min-train", type=int, default=30)
    ap.add_argument("--out", default="reports/telemetry.md")
    args = ap.parse_args(argv)
    races = load_races(Path(args.results_dir))
    res = run(races, args.min_train)
    if res is None:
        raise SystemExit("No practice data found. Run: uv run python scripts/extract_practice_features.py --from 2022 --to 2026")
    if len(res["races"]) < 10:
        raise SystemExit(f"Only {len(res['races'])} scorable races; download more weekends first.")
    text = report(res, args.min_train)
    Path(args.out).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
