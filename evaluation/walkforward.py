"""Walk-forward (expanding window) evaluation: train on the past, predict the next race."""
from __future__ import annotations

from .data import Race
from .metrics import RaceScore, score_race
from .models import build_feature_table


def walk_forward(races: list[Race], models, min_train: int = 15, table=None, external=None):
    """Return {model_name: [RaceScore, ...]} for races[min_train:].

    external: optional {name: {race_key: {driver_id: prob}}}; only races with predictions are scored
    (for every model) so all rows are compared on the same set of races.
    """
    table = table or build_feature_table(races)
    results = {m.name: [] for m in models}
    if external:
        for name in external:
            results[name] = []
    for t in range(min_train, len(races)):
        race = races[t]
        if external and any(race.key not in preds for preds in external.values()):
            continue
        drivers = [e.driver_id for e in race.entries]
        for m in models:
            m.fit(races[:t], table[:t])
            probs = m.predict(race, table[t])
            results[m.name].append(score_race(race.key, probs, race.winner_id))
        for name, preds in (external or {}).items():
            known = {d: p for d, p in preds[race.key].items() if d in drivers}
            # drivers the external model did not cover get probability zero
            probs = {d: known.get(d, 0.0) for d in drivers}
            results[name].append(score_race(race.key, probs, race.winner_id))
    return results
