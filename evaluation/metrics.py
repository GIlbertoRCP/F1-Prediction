"""Winner-prediction metrics, bootstrap confidence intervals and calibration."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

EPS = 1e-9


@dataclass
class RaceScore:
    key: tuple[int, int]
    winner_id: str
    p_winner: float
    logloss: float      # -ln P(actual winner)
    brier: float        # multiclass Brier score (sum over drivers)
    rank: int           # 1 = the model's top pick won
    top1: bool
    top3: bool
    pairs: list[tuple[float, int]]   # (predicted prob, did that driver win) for calibration


def score_race(key, probs: dict[str, float], winner_id: str) -> RaceScore:
    """Score one race. Exact probability ties are broken by driver id (arbitrary but fixed),
    so a model that outputs equal probabilities gets no hidden credit from grid order."""
    total = sum(probs.values())
    probs = {d: p / total for d, p in probs.items()}
    order = sorted(probs, key=lambda d: (-probs[d], d))
    rank = order.index(winner_id) + 1
    p_w = probs[winner_id]
    brier = sum((p - (1.0 if d == winner_id else 0.0)) ** 2 for d, p in probs.items())
    return RaceScore(
        key=key, winner_id=winner_id, p_winner=p_w,
        logloss=-math.log(max(p_w, EPS)), brier=brier, rank=rank,
        top1=rank == 1, top3=rank <= 3,
        pairs=[(p, 1 if d == winner_id else 0) for d, p in probs.items()],
    )


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 0, alpha: float = 0.05):
    """Percentile bootstrap CI of the mean, resampling races with replacement."""
    if not values:
        return (float("nan"), float("nan"))
    rng = random.Random(seed)
    n = len(values)
    means = sorted(sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(n_boot))
    lo = means[int((alpha / 2) * n_boot)]
    hi = means[min(n_boot - 1, int((1 - alpha / 2) * n_boot))]
    return (lo, hi)


def paired_diff_ci(a: list[float], b: list[float], n_boot: int = 2000, seed: int = 0):
    """Mean of (a - b) per race with a bootstrap CI. Lists must be race-aligned."""
    diffs = [x - y for x, y in zip(a, b)]
    return mean(diffs), bootstrap_ci(diffs, n_boot, seed)


CAL_EDGES = [0.0, 0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 1.0000001]


def calibration_table(scores: list[RaceScore]):
    """Pooled over every driver in every race: predicted vs observed win frequency per bucket."""
    buckets = [[0, 0.0, 0] for _ in range(len(CAL_EDGES) - 1)]  # n, sum_pred, wins
    for s in scores:
        for p, y in s.pairs:
            for i in range(len(CAL_EDGES) - 1):
                if CAL_EDGES[i] <= p < CAL_EDGES[i + 1]:
                    buckets[i][0] += 1
                    buckets[i][1] += p
                    buckets[i][2] += y
                    break
    rows = []
    for i, (n, sp, w) in enumerate(buckets):
        if n:
            rows.append((CAL_EDGES[i], min(CAL_EDGES[i + 1], 1.0), n, sp / n, w / n))
    return rows


def summarize(scores: list[RaceScore], seed: int = 0) -> dict:
    ll = [s.logloss for s in scores]
    return {
        "n_races": len(scores),
        "top1": (mean(1.0 if s.top1 else 0.0 for s in scores), bootstrap_ci([1.0 if s.top1 else 0.0 for s in scores], seed=seed)),
        "top3": (mean(1.0 if s.top3 else 0.0 for s in scores), bootstrap_ci([1.0 if s.top3 else 0.0 for s in scores], seed=seed)),
        "mean_rank": (mean(s.rank for s in scores), bootstrap_ci([float(s.rank) for s in scores], seed=seed)),
        "logloss": (mean(ll), bootstrap_ci(ll, seed=seed)),
        "brier": (mean(s.brier for s in scores), bootstrap_ci([s.brier for s in scores], seed=seed)),
    }
