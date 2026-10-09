"""Does the rank-ordered model hold up? Walk-forward comparison with the winner-only model, plus
calibration of podium and top-10 probabilities.

    python3 -m evaluation.ordered --out reports/ordered.md
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from .data import load_races
from .metrics import RaceScore, bootstrap_ci, calibration_table, mean, paired_diff_ci, score_race
from .models import BASE_FEATURES, ConditionalLogit, build_feature_table
from .ordered import ExplodedLogit, ScaledPL, simulate_positions


def _tail(counts, k, n_sims):
    return {d: sum(c[:k]) / n_sims for d, c in counts.items()}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="data/results")
    ap.add_argument("--min-train", type=int, default=15)
    ap.add_argument("--sims", type=int, default=600)
    ap.add_argument("--out", default="reports/ordered.md")
    ap.add_argument("--cache", default="reports/.ordered_cache.jsonl")
    ap.add_argument("--budget", type=float, default=0, help="stop after this many seconds (resume by re-running)")
    args = ap.parse_args(argv)
    races = load_races(Path(args.results_dir))
    table = build_feature_table(races)
    models = [ConditionalLogit("winner_only", BASE_FEATURES), ExplodedLogit("exploded_3", depth=3),
              ExplodedLogit("exploded_10", depth=10), ScaledPL("scaled_pl")]
    cache = Path(args.cache)
    done = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            rec = json.loads(line)
            done[rec["t"]] = rec
    started = time.time()
    # Resumable: results are appended per race, so a time-limited run can be repeated until complete.
    for t in range(args.min_train, len(races)):
        if t in done:
            continue
        if args.budget and time.time() - started > args.budget:
            print(f"time budget reached; {len(done)} of {len(races) - args.min_train} races done. Run again to continue.")
            return
        race = races[t]
        rec = {"t": t, "win": {}, "p3": {}, "p10": {}}
        for m in models:
            m.fit(races[:t], table[:t])
            rec["win"][m.name] = m.predict(race, table[t])
            if m.name != "winner_only":
                scales = m.scales if isinstance(m, ScaledPL) else None
                counts, _ = simulate_positions(m.utilities(table[t]), scales, args.sims, seed=t)
                rec["p3"][m.name], rec["p10"][m.name] = _tail(counts, 3, args.sims), _tail(counts, 10, args.sims)
                if isinstance(m, ScaledPL):
                    rec["p3"][m.name] = m.podium_probs(m.utilities(table[t]))   # exact
        with open(cache, "a") as f:
            f.write(json.dumps(rec) + "\n")
        done[t] = rec
    win = {m.name: [] for m in models}
    pod = {m.name: [] for m in models if m.name != "winner_only"}
    top10 = {m.name: [] for m in models if m.name != "winner_only"}
    for t in sorted(done):
        race, rec = races[t], done[t]
        fin = {e.driver_id: e.finish_position for e in race.entries if e.classified and e.finish_position}
        for name in win:
            win[name].append(score_race(race.key, rec["win"][name], race.winner_id))
        for store, key, k in ((pod, "p3", 3), (top10, "p10", 10)):
            for name in store:
                p = rec[key][name]
                pairs = [(p[d], 1 if fin.get(d, 99) <= k else 0) for d in p]
                store[name].append(RaceScore(race.key, race.winner_id, 0, 0, sum((a - b) ** 2 for a, b in pairs), 0, False, False, pairs))
    out = ["# Rank-ordered model: finishing-order probabilities\n",
           f"_Walk-forward over {len(win['winner_only'])} races; podium and top-10 odds from {args.sims} simulated races each._\n",
           "## Win probabilities (log loss, lower is better)\n",
           "| Model | Log loss | vs `winner_only` (paired, 95% CI) |", "|---|---|---|"]
    base = [s.logloss for s in win["winner_only"]]
    for name, scores in win.items():
        ll = [s.logloss for s in scores]
        lo, hi = bootstrap_ci(ll)
        if name == "winner_only":
            out.append(f"| `{name}` | {mean(ll):.3f} [{lo:.3f}, {hi:.3f}] | – |")
        else:
            d, (dl, dh) = paired_diff_ci(ll, base)
            verdict = "better" if dh < 0 else ("worse" if dl > 0 else "not distinguishable")
            out.append(f"| `{name}` | {mean(ll):.3f} [{lo:.3f}, {hi:.3f}] | {d:+.3f} [{dl:+.3f}, {dh:+.3f}] → {verdict} |")
    for title, store in (("Podium (top 3)", pod), ("Top 10", top10)):
        out.append(f"\n## {title}: calibration\n")
        for name, scores in store.items():
            if not scores:
                continue
            brier = mean(s.brier for s in scores) / 20
            out.append(f"### `{name}` (mean squared error per driver: {brier:.4f})\n")
            out.append("| Predicted bucket | Driver-races | Mean predicted | Observed |\n|---|---|---|---|")
            for lo_, hi_, n, pr, ob in calibration_table(scores):
                out.append(f"| {lo_*100:.0f}–{hi_*100:.0f}% | {n} | {pr*100:.1f}% | {ob*100:.1f}% |")
            out.append("")
    Path(args.out).write_text("\n".join(out) + "\n")
    print("\n".join(out[:12]))


if __name__ == "__main__":
    main()
