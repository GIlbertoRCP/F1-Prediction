"""Baseline win-probability models.

Every model sees only information available before the race (starting grid and
results of earlier races). The shared feature table is built in one chronological
pass where a race's features are computed *before* its own result is added, so
features for race t can never contain information from race t or later.
"""
from __future__ import annotations

import math
import statistics
from collections import defaultdict

from .data import Race

BASE_FEATURES = ["log_grid", "team_score", "driver_score", "driver_win", "team_win"]
# Qualifying-pace features (percent off the fastest qualifying lap of the weekend):
#   q_gap          this driver's gap on Saturday
#   team_q_gap     the team's best gap on Saturday (car pace, independent of one driver's mistake)
#   log_quali_pos  log of the qualifying classification (differs from the grid after penalties)
#   driver_q_form / team_q_form  exponentially weighted gap over earlier weekends
QUALI_FEATURES = ["q_gap", "team_q_gap", "log_quali_pos", "driver_q_form", "team_q_form"]
# Practice pace (sessions before qualifying only; filled in when data/telemetry exists):
#   fp_gap / team_fp_gap     best clean practice lap vs the fastest, driver and team's best car
#   fp_long / team_fp_long   long-run pace vs the best long run on the same tyre
#   driver_fp_form / team_fp_form  exponentially weighted fp_gap over earlier weekends
PRACTICE_FEATURES = ["fp_gap", "team_fp_gap", "fp_long", "team_fp_long", "driver_fp_form", "team_fp_form"]
FEATURES = BASE_FEATURES + QUALI_FEATURES + PRACTICE_FEATURES
HALFLIFE = 6.0  # in appearances
Q_GAP_CAP = 5.0       # percent; also used when a driver set no time
Q_GAP_DEFAULT = 2.0   # form prior for a driver/team with no history
FP_DEFAULT = 1.5      # practice gap used for a whole weekend with no practice data


class _EW:
    """Exponentially weighted running mean."""
    __slots__ = ("num", "den")

    def __init__(self):
        self.num = 0.0
        self.den = 0.0

    def update(self, value: float, decay: float) -> None:
        self.num = self.num * decay + value
        self.den = self.den * decay + 1.0

    def mean(self, default: float) -> float:
        return self.num / self.den if self.den > 0 else default


def finish_score(entry, n: int) -> float:
    """1.0 for a win down to 0.0 for last classified place; 0.0 if not classified."""
    if not entry.classified or entry.finish_position is None:
        return 0.0
    return 1.0 - (entry.finish_position - 1) / max(n - 1, 1)


def _gap(entry) -> float:
    g = entry.q_gap
    return Q_GAP_CAP if g is None else min(max(g, 0.0), Q_GAP_CAP)


def _practice(race) -> tuple[dict, dict]:
    """Per-driver practice gaps for one race with missing values filled from the same weekend:
    a driver with no measurement gets the field's median; a weekend with none gets a constant."""
    out = []
    for attr in ("fp_gap", "fp_long"):
        vals = {e.driver_id: getattr(e, attr) for e in race.entries if getattr(e, attr) is not None}
        fill = statistics.median(vals.values()) if vals else FP_DEFAULT
        out.append({e.driver_id: min(vals.get(e.driver_id, fill), Q_GAP_CAP) for e in race.entries})
    return out[0], out[1]


def build_feature_table(races: list[Race], halflife: float = HALFLIFE):
    """table[i] = list of (driver_id, feature_vector, won) for races[i], using races[:i] only."""
    decay = 0.5 ** (1.0 / halflife)
    d_score, d_win = defaultdict(_EW), defaultdict(_EW)
    t_score, t_win = defaultdict(_EW), defaultdict(_EW)
    d_q, t_q = defaultdict(_EW), defaultdict(_EW)
    d_fp, t_fp = defaultdict(_EW), defaultdict(_EW)
    table = []
    for race in races:
        n = len(race.entries)
        winner = race.winner_id
        gaps = {e.driver_id: _gap(e) for e in race.entries}
        team_best = {}
        for e in race.entries:
            team_best[e.team] = min(team_best.get(e.team, Q_GAP_CAP), gaps[e.driver_id])
        fp_gap, fp_long = _practice(race)
        team_fp, team_fpl = {}, {}
        for e in race.entries:
            team_fp[e.team] = min(team_fp.get(e.team, Q_GAP_CAP), fp_gap[e.driver_id])
            team_fpl[e.team] = min(team_fpl.get(e.team, Q_GAP_CAP), fp_long[e.driver_id])
        rows = []
        for e in race.entries:
            rows.append((
                e.driver_id,
                [
                    math.log(e.grid),
                    t_score[e.team].mean(0.5),
                    d_score[e.driver_id].mean(0.5),
                    d_win[e.driver_id].mean(0.0),
                    t_win[e.team].mean(0.0),
                    gaps[e.driver_id],
                    team_best[e.team],
                    math.log(e.quali_position if e.quali_position else e.grid),
                    d_q[e.driver_id].mean(Q_GAP_DEFAULT),
                    t_q[e.team].mean(Q_GAP_DEFAULT),
                    fp_gap[e.driver_id],
                    team_fp[e.team],
                    fp_long[e.driver_id],
                    team_fpl[e.team],
                    d_fp[e.driver_id].mean(FP_DEFAULT),
                    t_fp[e.team].mean(FP_DEFAULT),
                ],
                e.driver_id == winner,
            ))
        table.append(rows)
        # update state AFTER the features for this race are fixed
        team_scores, team_won = defaultdict(list), defaultdict(float)
        for e in race.entries:
            s = finish_score(e, n)
            d_score[e.driver_id].update(s, decay)
            d_win[e.driver_id].update(1.0 if e.driver_id == winner else 0.0, decay)
            team_scores[e.team].append(s)
            if e.driver_id == winner:
                team_won[e.team] = 1.0
        for e in race.entries:
            d_q[e.driver_id].update(gaps[e.driver_id], decay)
        for team, g in team_best.items():
            t_q[team].update(g, decay)
        if any(e.fp_gap is not None for e in race.entries):      # only weekends that have practice data
            for e in race.entries:
                d_fp[e.driver_id].update(fp_gap[e.driver_id], decay)
            for team, g in team_fp.items():
                t_fp[team].update(g, decay)
        for team, ss in team_scores.items():
            t_score[team].update(sum(ss) / len(ss), decay)
            t_win[team].update(team_won.get(team, 0.0), decay)
    return table


# --------------------------------------------------------------------------- models
class Uniform:
    name = "uniform"

    def fit(self, races, table):
        return self

    def predict(self, race, rows):
        return {r[0]: 1.0 / len(rows) for r in rows}


class GridPrior:
    """P(win | starting slot), learned from earlier races with light smoothing."""
    name = "grid_prior"
    MAX_SLOT = 20

    def fit(self, races, table):
        self.wins = [0.0] * (self.MAX_SLOT + 1)
        self.n = [0.0] * (self.MAX_SLOT + 1)
        for race in races:
            w = race.winner_id
            for e in race.entries:
                slot = min(e.grid, self.MAX_SLOT)
                self.n[slot] += 1
                if e.driver_id == w:
                    self.wins[slot] += 1
        return self

    def predict(self, race, rows):
        raw = {}
        for e in race.entries:
            slot = min(e.grid, self.MAX_SLOT)
            raw[e.driver_id] = (self.wins[slot] + 0.1) / (self.n[slot] + 0.1 * self.MAX_SLOT)
        z = sum(raw.values())
        return {d: p / z for d, p in raw.items()}


def _solve(A, b):
    """Solve A x = b by Gaussian elimination with partial pivoting."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        piv = M[c][c] if abs(M[c][c]) > 1e-12 else 1e-12
        for r in range(c + 1, n):
            f = M[r][c] / piv
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / (M[i][i] if abs(M[i][i]) > 1e-12 else 1e-12)
    return x


class ConditionalLogit:
    """Multinomial (conditional) logit: P(driver i wins) = softmax(w . x_i) within a race."""

    def __init__(self, name: str, features: list[str], l2: float = 1.0, max_iter: int = 30):
        self.name = name
        self.idx = [FEATURES.index(f) for f in features]
        self.features = features
        self.l2 = l2
        self.max_iter = max_iter
        self.w = [0.0] * len(features)
        self.mu = [0.0] * len(features)
        self.sd = [1.0] * len(features)

    def _x(self, vec):
        return [(vec[i] - self.mu[j]) / self.sd[j] for j, i in enumerate(self.idx)]

    def _penalised_loglik(self, Z, w):
        d = len(w)
        ll = 0.0
        for zs, win in Z:
            s = [sum(w[j] * z[j] for j in range(d)) for z in zs]
            m = max(s)
            ll += s[win] - (m + math.log(sum(math.exp(v - m) for v in s)))
        return ll - 0.5 * self.l2 * sum(v * v for v in w)

    def fit(self, races, table):
        groups = [rows for rows in table if any(r[2] for r in rows)]
        d = len(self.idx)
        flat = [[r[1][i] for i in self.idx] for rows in groups for r in rows]
        if not flat:
            return self
        self.mu = [sum(v[j] for v in flat) / len(flat) for j in range(d)]
        self.sd = [
            (sum((v[j] - self.mu[j]) ** 2 for v in flat) / len(flat)) ** 0.5 or 1.0 for j in range(d)
        ]
        Z = [([self._x(r[1]) for r in rows], [r[2] for r in rows].index(True)) for rows in groups]
        w = [0.0] * d
        best = self._penalised_loglik(Z, w)
        for _ in range(self.max_iter):
            g = [-self.l2 * wj for wj in w]
            H = [[0.0] * d for _ in range(d)]  # NEGATIVE Hessian of the penalised log-likelihood (positive definite)
            for j in range(d):
                H[j][j] = self.l2
            for zs, win in Z:
                s = [sum(w[j] * z[j] for j in range(d)) for z in zs]
                m = max(s)
                e = [math.exp(v - m) for v in s]
                tot = sum(e)
                p = [v / tot for v in e]
                mean = [sum(p[i] * zs[i][j] for i in range(len(zs))) for j in range(d)]
                for j in range(d):
                    g[j] += zs[win][j] - mean[j]
                for i in range(len(zs)):
                    zi, pi = zs[i], p[i]
                    for a in range(d):
                        pa = pi * zi[a]
                        for b in range(a, d):
                            H[a][b] += pa * zi[b]
                for a in range(d):
                    for b in range(a, d):
                        H[a][b] -= mean[a] * mean[b]
            for a in range(d):
                for b in range(a):
                    H[a][b] = H[b][a]
            step = _solve(H, g)
            # backtracking line search: only accept steps that increase the objective
            t, accepted = 1.0, False
            for _ in range(30):
                cand = [w[j] + t * step[j] for j in range(d)]
                val = self._penalised_loglik(Z, cand)
                if val >= best - 1e-12:
                    accepted = True
                    break
                t *= 0.5
            if not accepted:
                break
            moved = max(abs(c - o) for c, o in zip(cand, w))
            w, best = cand, val
            if moved < 1e-7:
                break
        self.w = w
        return self

    def predict(self, race, rows):
        s = [sum(self.w[j] * z for j, z in enumerate(self._x(r[1]))) for r in rows]
        m = max(s)
        e = [math.exp(v - m) for v in s]
        tot = sum(e)
        return {r[0]: v / tot for r, v in zip(rows, e)}


def default_models():
    return [
        Uniform(),
        GridPrior(),
        ConditionalLogit("form_only", ["team_score", "driver_score", "driver_win", "team_win"]),
        ConditionalLogit("grid_plus_form", BASE_FEATURES),
        ConditionalLogit("grid_form_qgap", BASE_FEATURES + ["q_gap", "team_q_gap"]),
        ConditionalLogit("grid_form_quali", FEATURES),
    ]
