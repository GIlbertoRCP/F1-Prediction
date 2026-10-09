"""Rank-ordered ("exploded") logit: extends the winner model to the whole top of the finishing order.

A race's finishing order is explained as a sequence of choices: first the winner is chosen from
everyone, then second place from everyone left, and so on for the top `depth` places. Each step is a
conditional logit with the same utilities, so one set of weights gives both win odds and, by
simulation, the odds of every finishing position (Plackett-Luce). Drivers who retire never appear
among the chosen finishers, so retirement risk is absorbed into their utility.
"""
from __future__ import annotations

import math
import random

from .models import BASE_FEATURES, ConditionalLogit


def explode(races, table, depth: int):
    """Turn each race into up to `depth` choice sets: (remaining drivers, who finished next)."""
    groups = []
    for race, rows in zip(races, table):
        order = sorted((e for e in race.entries if e.classified and e.finish_position),
                       key=lambda e: e.finish_position)[:depth]
        by_id = {r[0]: r for r in rows}
        chosen: set[str] = set()
        for e in order:
            remaining = [by_id[d] for d in by_id if d not in chosen]
            groups.append([(r[0], r[1], r[0] == e.driver_id) for r in remaining])
            chosen.add(e.driver_id)
    return groups


class ExplodedLogit:
    def __init__(self, name: str, features: list[str] = BASE_FEATURES, depth: int = 10, l2: float = 1.0):
        self.name, self.depth = name, depth
        self.inner = ConditionalLogit(name, features, l2=l2)

    def fit(self, races, table):
        self.inner.fit(races, explode(races, table, self.depth))
        return self

    def utilities(self, rows) -> dict[str, float]:
        w = self.inner.w
        return {r[0]: sum(w[j] * z for j, z in enumerate(self.inner._x(r[1]))) for r in rows}

    def predict(self, race, rows):
        u = self.utilities(rows)
        m = max(u.values())
        e = {d: math.exp(v - m) for d, v in u.items()}
        tot = sum(e.values())
        return {d: v / tot for d, v in e.items()}


class ScaledPL:
    """Winner model plus one 'sharpness' scale per later finishing position.

    Win odds are exactly the winner-only model. Behind the winner the order is chosen one place at a
    time, each from the drivers left, with chances proportional to exp(scale_j * utility). A scale
    below 1 means the order is less predictable further down (retirements, strategy, safety cars).
    The scales are fitted by maximum likelihood on earlier races only.
    """
    def __init__(self, name: str = "scaled_pl", features: list[str] = BASE_FEATURES, depth: int = 10, l2: float = 1.0):
        self.name, self.depth = name, depth
        self.base = ConditionalLogit(name, features, l2=l2)
        self.scales = [1.0] * depth

    def utilities(self, rows) -> dict[str, float]:
        w = self.base.w
        return {r[0]: sum(w[j] * z for j, z in enumerate(self.base._x(r[1]))) for r in rows}

    def fit(self, races, table):
        self.base.fit(races, table)
        per_race = []
        for race, rows in zip(races, table):
            u = self.utilities(rows)
            order = [e.driver_id for e in sorted((e for e in race.entries if e.classified and e.finish_position),
                                                 key=lambda e: e.finish_position)[:self.depth]]
            per_race.append((u, order))
        self.scales = [1.0] + [self._fit_scale(per_race, step) for step in range(1, self.depth)]
        return self

    @staticmethod
    def _fit_scale(per_race, step, prior_weight: float = 5.0) -> float:
        data = []
        for u, order in per_race:
            if len(order) <= step:
                continue
            gone = set(order[:step])
            rem = [u[d] for d in u if d not in gone]
            data.append((rem, u[order[step]]))

        def objective(lam):
            ll = 0.0
            for rem, chosen in data:
                m = max(lam * v for v in rem)
                ll += lam * chosen - (m + math.log(sum(math.exp(lam * v - m) for v in rem)))
            return ll - 0.5 * prior_weight * (lam - 1.0) ** 2

        lo, hi = 0.0, 3.0               # concave in lam: golden-section search
        g = (math.sqrt(5) - 1) / 2
        c, d = hi - g * (hi - lo), lo + g * (hi - lo)
        for _ in range(26):
            if objective(c) > objective(d):
                hi = d
            else:
                lo = c
            c, d = hi - g * (hi - lo), lo + g * (hi - lo)
        return (lo + hi) / 2

    def predict(self, race, rows):
        u = self.utilities(rows)
        m = max(u.values())
        e = {d: math.exp(v - m) for d, v in u.items()}
        tot = sum(e.values())
        return {d: v / tot for d, v in e.items()}

    def podium_probs(self, u: dict[str, float]) -> dict[str, float]:
        """Exact P(finish in the top 3) for every driver (sums over all ordered triples)."""
        ids = list(u)
        out = {d: 0.0 for d in ids}
        s1, s2, s3 = self.scales[0], self.scales[1], self.scales[2]
        w1 = {d: math.exp(s1 * u[d]) for d in ids}
        w2 = {d: math.exp(s2 * u[d]) for d in ids}
        w3 = {d: math.exp(s3 * u[d]) for d in ids}
        t1 = sum(w1.values())
        for a in ids:
            pa = w1[a] / t1
            t2 = sum(w2[d] for d in ids if d != a)
            for b in ids:
                if b == a:
                    continue
                pb = pa * w2[b] / t2
                t3 = sum(w3[d] for d in ids if d != a and d != b)
                for c in ids:
                    if c == a or c == b:
                        continue
                    pc = pb * w3[c] / t3
                    out[a] += pc
                    out[b] += pc
                    out[c] += pc
        # each triple was added to a, b and c once, so out[d] = P(d in top 3)
        return out


def simulate_positions(utilities: dict[str, float], scales: list[float] | None = None, n_sims: int = 4000,
                       seed: int = 0, out: set[str] | None = None):
    """Monte Carlo of the finishing order, one place at a time from the drivers left.
    `scales[j]` sharpens or flattens place j+1 (the last scale is reused further down).
    Drivers in `out` retire and finish behind everybody. Returns ({driver: [count per place]}, n_out)."""
    rng = random.Random(seed)
    out = out or set()
    ids = [d for d in utilities if d not in out]
    n = len(ids)
    scales = scales or [1.0]
    counts = {d: [0] * len(utilities) for d in utilities}
    for _ in range(n_sims):
        left = list(ids)
        for pos in range(n):
            lam = scales[min(pos, len(scales) - 1)]
            ws = [math.exp(lam * utilities[d]) for d in left]
            r = rng.random() * sum(ws)
            acc = 0.0
            for k, w in enumerate(ws):
                acc += w
                if r <= acc:
                    break
            counts[left[k]][pos] += 1
            left.pop(k)
    return counts, len(out)
