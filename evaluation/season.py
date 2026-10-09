"""Championship simulation: play out the rest of a season many times and count who wins the title.

What it uses (all of it known before the races it simulates):
  * the points each driver and team already have, straight from the results files;
  * a form-only race model (no starting grid, because the grids are not set yet): the production
    conditional logit's form features plus recent championship points scored, and the fitted
    per-place sharpness scales, so it gives a whole finishing order, not just a winner;
  * the remaining calendar, including which weekends have a sprint.

What it deliberately does not know: upgrades, penalties, who is injured, track-specific form. To stand
in for the fact that a car's true pace drifts during a season, every simulated season draws a shared
shift for each team and a smaller one for each driver. How big those shifts are (TAU) is the one number
fitted on past seasons (evaluation/season_eval.py), and reports/championship.md shows how it was chosen.
"""
from __future__ import annotations

import math
import random
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .data import Race
from .jolpica import read_rows
from .models import FEATURES, _EW, build_feature_table
from .ordered import ScaledPL

FORM = ["team_score", "driver_score", "driver_win", "team_win"]
RACE_POINTS = [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]
SPRINT_POINTS_2021 = [3, 2, 1]
SPRINT_POINTS = [8, 7, 6, 5, 4, 3, 2, 1]
DRIVER_SHIFT_RATIO = 0.5   # a driver's own drift is half the size of a team's
TAU = 0.90                  # sd of a team's shared utility shift per simulated season (fitted: see reports/championship.md)
MIN_TRAIN = 15
PTS_HALFLIVES = (3.0, 6.0)   # memory (in races) of the recent-points features
PTS_DEFAULT = 0.1           # form prior for a driver or team with no history


def sprint_scheme(season: int) -> list[int]:
    return SPRINT_POINTS_2021 if season <= 2021 else SPRINT_POINTS


@dataclass
class Standing:
    driver_points: dict[str, float] = field(default_factory=dict)
    team_points: dict[str, float] = field(default_factory=dict)
    driver_team: dict[str, str] = field(default_factory=dict)      # latest team
    driver_code: dict[str, str] = field(default_factory=dict)


def load_sprint_points(results_dir: Path) -> dict[tuple[int, int, str], tuple[float, str]]:
    """(season, round, driver_id) -> (points, team)"""
    out = {}
    for r in read_rows(Path(results_dir) / "sprints.csv"):
        out[(r["season"], r["round"], r["driver_id"])] = (float(r.get("points") or 0), r["team"])
    return out


def standing_after(races: list[Race], sprints: dict, season: int, upto_round: int) -> Standing:
    """Championship standing from the results files after `upto_round` of `season`."""
    s = Standing()
    for race in races:
        if race.season != season or race.round > upto_round:
            continue
        for e in race.entries:
            s.driver_points[e.driver_id] = s.driver_points.get(e.driver_id, 0.0) + e.points
            s.team_points[e.team] = s.team_points.get(e.team, 0.0) + e.points
            s.driver_team[e.driver_id] = e.team
            s.driver_code[e.driver_id] = e.driver
    for (ssn, rnd, did), (pts, team) in sprints.items():
        if ssn == season and rnd <= upto_round:
            s.driver_points[did] = s.driver_points.get(did, 0.0) + pts
            s.team_points[team] = s.team_points.get(team, 0.0) + pts
    return s


def points_form_table(races: list[Race], halflives=PTS_HALFLIVES):
    """Feature table = the production form features plus how many championship points each driver and team
    has been scoring lately (exponentially weighted, as a fraction of a win's 25), at two memory lengths.
    Row vectors are the `FEATURES` vector followed by the extra columns; race i's features use races before i."""
    table = build_feature_table(races)
    decay = [0.5 ** (1.0 / h) for h in halflives]
    d_state = [defaultdict(_EW) for _ in halflives]
    t_state = [defaultdict(_EW) for _ in halflives]
    out = []
    for race, rows in zip(races, table):
        entries = {e.driver_id: e for e in race.entries}
        new_rows = []
        for did, vec, won in rows:
            e = entries[did]
            extra = []
            for k in range(len(halflives)):
                extra += [d_state[k][did].mean(PTS_DEFAULT), t_state[k][e.team].mean(PTS_DEFAULT)]
            new_rows.append((did, vec + extra, won))
        out.append(new_rows)
        for k in range(len(halflives)):          # update only after this race's features are fixed
            by_team = defaultdict(list)
            for e in race.entries:
                d_state[k][e.driver_id].update(e.points / 25.0, decay[k])
                by_team[e.team].append(e.points / 25.0)
            for team, v in by_team.items():
                t_state[k][team].update(sum(v) / len(v), decay[k])
    return out


def fit_form_model(history: list[Race], lineup: Race) -> tuple[dict[str, float], list[float]]:
    """Utilities for every driver in `lineup` (form only, nothing about a grid) and per-place scales.
    `history` is every race before the point we forecast from; `lineup` is the most recent race, whose
    entries are assumed to be the field for the remaining rounds."""
    if len(history) < MIN_TRAIN:
        raise ValueError(f"need at least {MIN_TRAIN} earlier races, got {len(history)}")
    nxt = Race(lineup.season, lineup.round + 1, "next", list(lineup.entries), "")
    table = points_form_table(history + [nxt])
    names = FORM + [f"{kind}_pts_{h:g}" for h in PTS_HALFLIVES for kind in ("driver", "team")]
    model = ScaledPL("pre_form", FORM)
    base = len(FEATURES)
    model.base.idx = [FEATURES.index(f) for f in FORM] + [base + i for i in range(len(names) - len(FORM))]
    model.base.features = names
    model.base.w, model.base.mu, model.base.sd = [0.0] * len(names), [0.0] * len(names), [1.0] * len(names)
    model.fit(history, table[:-1])
    return model.utilities(table[-1]), model.scales


def _pick(weights: list[float], rng: random.Random) -> int:
    r = rng.random() * sum(weights)
    acc = 0.0
    for k, w in enumerate(weights):
        acc += w
        if r <= acc:
            return k
    return len(weights) - 1


def simulate_season(utilities: dict[str, float], scales: list[float], teams: dict[str, str],
                    standing: Standing, remaining: list[dict], season: int, n_sims: int = 2000,
                    tau: float = TAU, seed: int = 0, out: set[str] | None = None) -> dict:
    """Play out `remaining` ([{'round': n, 'sprint': bool}, ...]) n_sims times.

    Returns driver/team final-points samples and title counts. `out` drivers do not race."""
    rng = random.Random(seed)
    out = out or set()
    ids = [d for d in utilities if d not in out]
    team_names = sorted({teams[d] for d in ids})
    n_scales = len(scales)
    sprint_pts = sprint_scheme(season)
    d_final = {d: [] for d in standing.driver_points.keys() | set(ids)}
    t_final = {t: [] for t in standing.team_points.keys() | set(team_names)}
    d_titles = {d: 0 for d in d_final}
    t_titles = {t: 0 for t in t_final}
    base_d = {d: standing.driver_points.get(d, 0.0) for d in d_final}
    base_t = {t: standing.team_points.get(t, 0.0) for t in t_final}
    for _ in range(n_sims):
        shift_t = {t: rng.gauss(0.0, tau) for t in team_names}
        u = {d: utilities[d] + shift_t[teams[d]] + rng.gauss(0.0, tau * DRIVER_SHIFT_RATIO) for d in ids}
        w = [[math.exp(scales[min(j, n_scales - 1)] * u[d]) for d in ids] for j in range(len(RACE_POINTS))]
        dp = dict(base_d)
        tp = dict(base_t)
        for ev in remaining:
            for kind, pts_table in (("race", RACE_POINTS), ("sprint", sprint_pts)):
                if kind == "sprint" and not ev.get("sprint"):
                    continue
                left = list(range(len(ids)))
                for j in range(min(len(pts_table), len(ids))):
                    k = _pick([w[j][i] for i in left], rng)
                    i = left.pop(k)
                    d = ids[i]
                    dp[d] += pts_table[j]
                    tp[teams[d]] += pts_table[j]
        for d, v in dp.items():
            d_final[d].append(v)
        for t, v in tp.items():
            t_final[t].append(v)
        d_titles[max(dp, key=lambda d: (dp[d], rng.random()))] += 1
        t_titles[max(tp, key=lambda t: (tp[t], rng.random()))] += 1
    return {"driver_final": d_final, "team_final": t_final, "driver_titles": d_titles,
            "team_titles": t_titles, "n": n_sims}


def summarise(samples: list[float]) -> dict:
    s = sorted(samples)
    n = len(s)

    def q(p):
        return s[min(n - 1, max(0, int(round(p * (n - 1)))))]
    return {"mean": sum(s) / n, "p10": q(0.10), "p50": q(0.50), "p90": q(0.90)}


def forecast_season(races: list[Race], sprints: dict, season: int, upto_round: int, remaining: list[dict],
                    n_sims: int = 2000, tau: float = TAU, seed: int = 0) -> dict:
    """Everything the product needs: standings, title odds and final-points ranges, from results
    through `upto_round` only."""
    hist = sorted((r for r in races if (r.season, r.round) <= (season, upto_round)),
                  key=lambda r: (r.season, r.round))
    lineup = hist[-1]
    utilities, scales = fit_form_model(hist, lineup)
    teams = {e.driver_id: e.team for e in lineup.entries}
    standing = standing_after(races, sprints, season, upto_round)
    sim = simulate_season(utilities, scales, teams, standing, remaining, season, n_sims, tau, seed)
    code = {d: c for d, c in standing.driver_code.items()}
    drivers = []
    for d, vals in sim["driver_final"].items():
        drivers.append({"id": d, "code": code.get(d, d.upper()[:3]), "team": standing.driver_team.get(d, ""),
                        "points": standing.driver_points.get(d, 0.0), "title": sim["driver_titles"][d] / n_sims,
                        "racing": d in teams, **summarise(vals)})
    team_rows = [{"team": t, "points": standing.team_points.get(t, 0.0), "title": sim["team_titles"][t] / n_sims,
                  **summarise(vals)} for t, vals in sim["team_final"].items()]
    drivers.sort(key=lambda r: (-r["title"], -r["mean"]))
    team_rows.sort(key=lambda r: (-r["title"], -r["mean"]))
    return {"season": season, "after_round": upto_round, "remaining": remaining, "n_sims": n_sims, "tau": tau,
            "drivers": drivers, "teams": team_rows, "scales": scales}
