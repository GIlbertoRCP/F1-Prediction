"""Backtest the championship simulation on past seasons, walk-forward.

For every season and every round (after round 3, with at least one race left) it forecasts the rest of
the season from the results through that round only, then compares with how the season really ended.

    python3 -m evaluation.season_eval --out reports/championship.md --history data/championship_history.json
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
from pathlib import Path

from .data import load_races
from .season import (TAU, fit_form_model, load_sprint_points, simulate_season, standing_after, summarise)

ROOT = Path(__file__).resolve().parent.parent
SEASONS = [2021, 2022, 2023, 2024, 2025]
TAUS = [0.0, 0.30, 0.60, 0.80, 0.90, 1.00, 1.20]
N_SIMS = 1000
FIRST_CUTOFF = 3
FLOOR = 0.002          # probability floor when scoring the eventual champion

_RACES = None
_SPRINTS = None


def _remaining(season: int, after: int) -> list[dict]:
    rounds = sorted({r.round for r in _RACES if r.season == season and r.round > after})
    sprint_rounds = {rnd for (s, rnd, _d) in _SPRINTS if s == season}
    return [{"round": r, "sprint": r in sprint_rounds} for r in rounds]


def _task(args):
    season, cutoff = args
    hist = sorted((r for r in _RACES if (r.season, r.round) <= (season, cutoff)), key=lambda r: (r.season, r.round))
    lineup = hist[-1]
    u, scales = fit_form_model(hist, lineup)
    teams = {e.driver_id: e.team for e in lineup.entries}
    now = standing_after(_RACES, _SPRINTS, season, cutoff)
    last = max(r.round for r in _RACES if r.season == season)
    final = standing_after(_RACES, _SPRINTS, season, last)
    rem = _remaining(season, cutoff)
    out = {"season": season, "cutoff": cutoff, "total_rounds": last, "taus": {}}
    for tau in TAUS:
        sim = simulate_season(u, scales, teams, now, rem, season, N_SIMS, tau, seed=season * 100 + cutoff)
        n = sim["n"]
        drivers = []
        for d, vals in sim["driver_final"].items():
            s = summarise(vals)
            drivers.append({"id": d, "now": now.driver_points.get(d, 0.0), "actual": final.driver_points.get(d, 0.0),
                            "title": sim["driver_titles"][d] / n, "code": now.driver_code.get(d, d),
                            "team": now.driver_team.get(d, ""), **s})
        team_rows = []
        for t, vals in sim["team_final"].items():
            s = summarise(vals)
            team_rows.append({"team": t, "now": now.team_points.get(t, 0.0), "actual": final.team_points.get(t, 0.0),
                              "title": sim["team_titles"][t] / n, **s})
        out["taus"][tau] = {"drivers": drivers, "teams": team_rows}
    return out


def run(races, sprints, workers: int = 4, seasons=SEASONS) -> list[dict]:
    global _RACES, _SPRINTS
    _RACES, _SPRINTS = races, sprints
    tasks = []
    for s in seasons:
        last = max(r.round for r in races if r.season == s)
        tasks += [(s, c) for c in range(FIRST_CUTOFF, last)]
    with mp.get_context("fork").Pool(workers) as pool:
        return pool.map(_task, tasks, chunksize=1)


def champion(rows, key="actual", name="id"):
    return max(rows, key=lambda r: r[key])[name]


def evaluate(results: list[dict], tau: float, seasons=None) -> dict:
    """Pooled metrics for one tau."""
    cov, n_cov, abs_err, base_err, n_err = 0, 0, 0.0, 0.0, 0
    ll, brier, k = 0.0, 0.0, 0
    tll, tk = 0.0, 0
    for res in results:
        if seasons and res["season"] not in seasons:
            continue
        frac_done = res["cutoff"] / res["total_rounds"]
        block = res["taus"][tau]
        champ = champion(block["drivers"])
        for d in block["drivers"]:
            if d["now"] < 5:       # a fixed rule that does not depend on the model
                continue
            n_cov += 1
            cov += d["p10"] <= d["actual"] <= d["p90"]
            abs_err += abs(d["mean"] - d["actual"])
            base_err += abs(d["now"] / frac_done - d["actual"])
            n_err += 1
        p = next(d["title"] for d in block["drivers"] if d["id"] == champ)
        ll += -math.log(max(p, FLOOR))
        brier += sum((d["title"] - (d["id"] == champ)) ** 2 for d in block["drivers"])
        k += 1
        tchamp = champion(block["teams"], name="team")
        tp = next(t["title"] for t in block["teams"] if t["team"] == tchamp)
        tll += -math.log(max(tp, FLOOR))
        tk += 1
    return {"coverage80": cov / n_cov if n_cov else float("nan"), "n_cov": n_cov,
            "mae": abs_err / n_err if n_err else float("nan"), "base_mae": base_err / n_err if n_err else float("nan"),
            "title_logloss": ll / k if k else float("nan"), "title_brier": brier / k if k else float("nan"),
            "team_logloss": tll / tk if tk else float("nan"), "n_cutoffs": k}


BASELINE_NOISE = [3.0, 5.0, 8.0, 12.0, 18.0]   # points of noise per sqrt(race remaining)


def baseline_title_logloss(results: list[dict], noise: float, seasons=None, n_draws: int = 2000) -> float:
    """A deliberately simple rival: project every driver's final points in a straight line from their points
    per race so far, add independent Gaussian noise growing with the square root of the races left, and count
    how often each driver finishes first. Scored like the simulation (log loss on the eventual champion)."""
    import random
    rng = random.Random(7)
    total, k = 0.0, 0
    for res in results:
        if seasons and res["season"] not in seasons:
            continue
        rows = res["taus"][TAUS[0]]["drivers"]
        left = res["total_rounds"] - res["cutoff"]
        proj = {d["id"]: d["now"] + d["now"] / res["cutoff"] * left for d in rows if d["now"] >= 5}
        sd = noise * math.sqrt(left)
        wins = {d: 0 for d in proj}
        for _ in range(n_draws):
            wins[max(proj, key=lambda d: proj[d] + rng.gauss(0, sd))] += 1
        champ = champion(rows)
        p = wins.get(champ, 0) / n_draws
        total += -math.log(max(p, FLOOR))
        k += 1
    return total / k


def trajectories(results: list[dict], tau: float, top: int = 6) -> dict:
    """Title odds of the leading contenders at every cutoff, for the site's history chart."""
    out = {}
    for res in results:
        block = res["taus"][tau]
        s = out.setdefault(str(res["season"]), {"total_rounds": res["total_rounds"], "cutoffs": []})
        s["cutoffs"].append({
            "after": res["cutoff"],
            "drivers": [{"code": d["code"], "team": d["team"], "title": round(d["title"], 4), "now": d["now"],
                         "mean": round(d["mean"], 1)}
                        for d in sorted(block["drivers"], key=lambda r: -r["title"])[:top]],
            "champion_actual": champion(block["drivers"], name="code")})
    for s in out.values():
        s["cutoffs"].sort(key=lambda c: c["after"])
    return out


def history_payload(results: list[dict], tau: float) -> dict:
    """What the site shows about the backtest: headline numbers plus title-odds trajectories."""
    m = evaluate(results, tau)
    base = {c: baseline_title_logloss(results, c) for c in BASELINE_NOISE}
    return {"tau": tau, "n_sims": N_SIMS, "seasons_tested": SEASONS,
            "summary": {"coverage80": round(m["coverage80"], 4), "mae": round(m["mae"], 2),
                        "straight_line_mae": round(m["base_mae"], 2), "title_logloss": round(m["title_logloss"], 4),
                        "rival_title_logloss": round(min(base.values()), 4), "cutoffs": m["n_cutoffs"],
                        "scored_drivers": m["n_cov"]},
            "seasons": trajectories(results, tau)}


def report(results: list[dict], chosen: float) -> str:
    L = ["# Championship simulation: how well does it work?", "",
         f"_Walk-forward: for each of {len(SEASONS)} past seasons ({SEASONS[0]}–{SEASONS[-1]}) and every round from "
         f"{FIRST_CUTOFF} on, the rest of the season is simulated ({N_SIMS} runs) from results through that round only, "
         "then compared with how the season really finished. Each season counts only once as a title outcome, so the "
         "title numbers below rest on five champions per cutoff; the points-range numbers have far more data._", "",
         "## Choosing the one fitted number (`TAU`, the size of the pace drift allowed in a season)", "",
         "| TAU | 80% range covers actual points | MAE of expected points | MAE of straight-line projection | "
         "log loss on champion | log loss on constructors' champion |", "|---|---|---|---|---|---|"]
    for tau in TAUS:
        m = evaluate(results, tau)
        L.append(f"| {tau:.2f} | {m['coverage80']:.0%} ({m['n_cov']}) | {m['mae']:.1f} | {m['base_mae']:.1f} | "
                 f"{m['title_logloss']:.3f} | {m['team_logloss']:.3f} |")
    L += ["", "A well-calibrated 80% range covers about 80%. A larger TAU widens the ranges; too small a TAU makes the "
          "simulation overconfident because it assumes every car keeps exactly its current pace.", "",
          f"Chosen: **TAU = {chosen:.2f}**.", "", "## Per season at the chosen TAU", "",
          "| Season | 80% range coverage | MAE expected pts | MAE straight-line | log loss on champion |", "|---|---|---|---|---|"]
    for s in SEASONS:
        m = evaluate(results, chosen, seasons=[s])
        L.append(f"| {s} | {m['coverage80']:.0%} | {m['mae']:.1f} | {m['base_mae']:.1f} | {m['title_logloss']:.3f} |")
    base = {c: baseline_title_logloss(results, c) for c in BASELINE_NOISE}
    best_c = min(base, key=base.get)
    L += ["", "## Against a simple rival", "",
          "Straight-line projection of each driver's points, plus random noise that grows with the races left "
          f"(noise level picked in hindsight, which flatters it): log loss on the eventual champion **{base[best_c]:.3f}** "
          f"at {best_c:g} points of noise per √race, versus **{evaluate(results, chosen)['title_logloss']:.3f}** for the simulation. "
          "Lower is better.", "",
          "| Points of noise per √race | Log loss on champion |", "|---|---|"]
    L += [f"| {c:g} | {v:.3f} |" for c, v in base.items()]
    pairs = []
    for res in results:
        block = res["taus"][chosen]
        champ = champion(block["drivers"])
        pairs += [(d["title"], d["id"] == champ) for d in block["drivers"]]
    L += ["", "## Do title odds mean what they say? (all cutoffs, all seasons)", "",
          "| Predicted title chance | Driver-cutoffs | Mean predicted | Won the title |", "|---|---|---|---|"]
    edges = [(0, .02), (.02, .1), (.1, .3), (.3, .6), (.6, .9), (.9, 1.0001)]
    for lo, hi in edges:
        b = [(p, w) for p, w in pairs if lo <= p < hi]
        if b:
            L.append(f"| {lo:.0%}–{min(hi, 1):.0%} | {len(b)} | {sum(p for p, _ in b) / len(b):.1%} | {sum(w for _, w in b) / len(b):.1%} |")
    L += ["", "Cutoffs within a season are strongly correlated, so these frequencies rest on far fewer independent "
          f"outcomes than the row counts suggest ({len(SEASONS)} champions).", "",
          "## Known limits", "",
          "- Fastest-lap bonus points (scored through 2024) are not simulated; they are in the actual totals, so the "
          "backtest slightly understates the points of the front-runners.",
          "- Everyone in the latest race's line-up is assumed to start every remaining round; injuries and "
          "replacements are not forecast.",
          "- Form is frozen at the cutoff; the TAU drift stands in for upgrades and development.",
          "- Selection effects: TAU was chosen so the 80% ranges hit 80% on these same seasons, and the two recent-points "
          "memory lengths (3 and 6 races) were chosen among a handful of variants on them too. The coverage figure is a fit, "
          "not a test; the comparisons with the straight-line rival are mildly flattering for the same reason."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default=str(ROOT / "data" / "results"))
    ap.add_argument("--out", default=str(ROOT / "reports" / "championship.md"))
    ap.add_argument("--history", default=str(ROOT / "data" / "championship_history.json"))
    ap.add_argument("--tau", type=float, default=TAU)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    races = load_races(Path(args.results_dir))
    sprints = load_sprint_points(Path(args.results_dir))
    results = run(races, sprints, args.workers)
    Path(args.out).write_text(report(results, args.tau))
    Path(args.history).write_text(json.dumps(history_payload(results, args.tau), separators=(",", ":")))
    print(f"wrote {args.out} and {args.history}")


if __name__ == "__main__":
    main()
