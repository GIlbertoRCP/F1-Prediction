"""The production forecasting engine: the `grid_plus_form` conditional logit.

It is the model that won the backtest (see reports/baselines.md): starting grid plus
exponentially weighted driver/team form. For a given race it trains only on races that
came before it, exactly like the walk-forward evaluation.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from evaluation.data import Entry, Race, parse_lap
from evaluation.jolpica import read_rows
from evaluation.models import BASE_FEATURES, ConditionalLogit, build_feature_table

MODEL_NAME = "grid_plus_form"
MIN_TRAIN = 15
_ROOT = Path(__file__).resolve().parent.parent


def model_version() -> str:
    """Short hash of the code that defines the model, stored with every prediction."""
    h = hashlib.sha256()
    for rel in ("evaluation/models.py", "oracle/engine.py"):
        h.update((_ROOT / rel).read_bytes())
    return h.hexdigest()[:10]


def forecast(history: list[Race], race: Race) -> dict[str, float]:
    """P(win) for each driver in `race`, using only `history` (races strictly before it)."""
    if len(history) < MIN_TRAIN:
        raise ValueError(f"need at least {MIN_TRAIN} earlier races, got {len(history)}")
    table = build_feature_table(history + [race])
    model = ConditionalLogit(MODEL_NAME, BASE_FEATURES).fit(history, table[:-1])
    return model.predict(race, table[-1])


def entries_payload(race: Race, probs: dict[str, float]) -> list[dict]:
    rows = [
        {"driver_id": e.driver_id, "driver": e.driver, "team": e.team, "grid": e.grid,
         "p": round(probs[e.driver_id], 6)}
        for e in race.entries
    ]
    return sorted(rows, key=lambda r: (-r["p"], r["driver_id"]))


def load_pending(results_dir: Path, finished: list[Race]) -> list[Race]:
    """Races that have a qualifying result but no race result yet (grid = qualifying order).

    Only weekends later than the last finished race count, so old gaps in the data are ignored.
    """
    done = {r.key for r in finished}
    last = max(done) if done else (0, 0)
    grouped: dict[tuple[int, int], list[dict]] = {}
    for r in read_rows(Path(results_dir) / "qualifying.csv"):
        key = (r["season"], r["round"])
        if key > last and key not in done:
            grouped.setdefault(key, []).append(r)
    out = []
    for key in sorted(grouped):
        rows = grouped[key]
        if len(rows) < 10:
            continue
        n = len(rows)
        entries = []
        for r in rows:
            pos = str(r.get("quali_position", "")).strip()
            laps = [t for t in (parse_lap(r.get(k)) for k in ("q1", "q2", "q3")) if t is not None]
            entries.append(Entry(
                driver=r["driver"], driver_id=r["driver_id"], team=r["team"],
                grid=int(pos) if pos.isdigit() else n + 1,
                finish_position=None, classified=False,
                quali_position=int(pos) if pos.isdigit() else None,
                q_gap=None if not laps else 0.0,
            ))
        out.append(Race(key[0], key[1], rows[0]["race"], entries, date=rows[0].get("date", "")))
    return out
