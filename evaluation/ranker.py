"""Turn an external model's per-driver rank scores into win probabilities, walk-forward.

A ranker outputs scores, not probabilities. We map scores to probabilities with ONE parameter, fit
only on earlier races' out-of-sample scores:

    P(driver i wins) = softmax_i( offset_i + beta * z_i )

z_i is the driver's score standardised within the race (higher = better).
 * `ranker_only`            offset = 0                      -> how good are the scores on their own?
 * `grid_form_plus_ranker`  offset = log P from the         -> do the scores add information beyond
                            grid+form baseline (itself          grid position and recent form?
                            fitted only on earlier races)

beta is shrunk toward 0 (L2), so with little data the stacked model falls back to the baseline.
"""
from __future__ import annotations

import math

from .models import BASE_FEATURES, ConditionalLogit


def zscores(scores: dict[str, float], drivers: list[str]) -> list[float] | None:
    """Standardised scores in `drivers` order. Drivers without a score get the race's worst score."""
    vals = [scores[d] for d in drivers if d in scores]
    if len(vals) < 2:
        return None
    mu = sum(vals) / len(vals)
    sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
    worst = (min(vals) - mu) / sd
    return [((scores[d] - mu) / sd) if d in scores else worst for d in drivers]


def fit_beta(groups, l2: float = 1.0, max_iter: int = 60) -> float:
    """groups: list of (offsets, z, winner_index). Maximise the penalised conditional log-likelihood."""
    def objective(b):
        total = 0.0
        for off, z, w in groups:
            s = [o + b * zz for o, zz in zip(off, z)]
            m = max(s)
            total += s[w] - (m + math.log(sum(math.exp(v - m) for v in s)))
        return total - 0.5 * l2 * b * b

    b, best = 0.0, objective(0.0)
    for _ in range(max_iter):
        g, h = -l2 * b, l2
        for off, z, w in groups:
            s = [o + b * zz for o, zz in zip(off, z)]
            m = max(s)
            e = [math.exp(v - m) for v in s]
            tot = sum(e)
            p = [v / tot for v in e]
            mean = sum(pi * zz for pi, zz in zip(p, z))
            g += z[w] - mean
            h += sum(pi * zz * zz for pi, zz in zip(p, z)) - mean * mean
        step = g / h
        t, moved = 1.0, False
        for _ in range(30):                      # backtracking line search
            cand = b + t * step
            val = objective(cand)
            if val >= best - 1e-12:
                moved = True
                break
            t *= 0.5
        if not moved:
            break
        delta, b, best = abs(cand - b), cand, val
        if delta < 1e-9:
            break
    return b


class RankerModel:
    def __init__(self, name: str, scores: dict, stack_on_baseline: bool = False, l2: float = 1.0):
        self.name = name
        self.scores = scores                # {(season, round): {driver_id: score}}
        self.stack = stack_on_baseline
        self.l2 = l2
        self.beta = 0.0
        self.n_train = 0
        self._base_cache: dict = {}
        self._hist = None

    @staticmethod
    def _make_base():
        return ConditionalLogit("grid_plus_form", BASE_FEATURES)

    def _base_logp(self, race, races_before, table_before, rows):
        """log P(win) from the grid+form baseline fitted only on races before `race`."""
        key = race.key
        if key not in self._base_cache:
            probs = self._make_base().fit(races_before, table_before).predict(race, rows)
            self._base_cache[key] = {d: math.log(max(p, 1e-12)) for d, p in probs.items()}
        return self._base_cache[key]

    def fit(self, races, table):
        self._hist = (races, table)
        groups = []
        for r, race in enumerate(races):
            sc = self.scores.get(race.key)
            if not sc:
                continue
            drivers = [row[0] for row in table[r]]
            z = zscores(sc, drivers)
            if z is None or race.winner_id not in drivers:
                continue
            if self.stack:
                lp = self._base_logp(race, races[:r], table[:r], table[r])
                off = [lp[d] for d in drivers]
            else:
                off = [0.0] * len(drivers)
            groups.append((off, z, drivers.index(race.winner_id)))
        self.n_train = len(groups)
        self.beta = fit_beta(groups, self.l2) if groups else 0.0
        return self

    def predict(self, race, rows):
        drivers = [row[0] for row in rows]
        z = zscores(self.scores[race.key], drivers) or [0.0] * len(drivers)
        if self.stack:
            races, table = self._hist
            lp = self._make_base().fit(races, table).predict(race, rows)
            off = [math.log(max(lp[d], 1e-12)) for d in drivers]
        else:
            off = [0.0] * len(drivers)
        s = [o + self.beta * zz for o, zz in zip(off, z)]
        m = max(s)
        e = [math.exp(v - m) for v in s]
        tot = sum(e)
        return {d: v / tot for d, v in zip(drivers, e)}
