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
from evaluation.models import BASE_FEATURES, build_feature_table
from evaluation.models import FEATURES as ALL_FEATURES
from evaluation.ordered import ScaledPL

FEATURES_INDEX = {f: i for i, f in enumerate(ALL_FEATURES)}

MODEL_NAME = "grid_plus_form"
MIN_TRAIN = 15
_ROOT = Path(__file__).resolve().parent.parent


def model_version() -> str:
    """Short hash of the code that defines the model, stored with every prediction."""
    h = hashlib.sha256()
    for rel in ("evaluation/models.py", "evaluation/ordered.py", "oracle/engine.py"):
        h.update((_ROOT / rel).read_bytes())
    return h.hexdigest()[:10]


def forecast_detail(history: list[Race], race: Race) -> dict:
    """Everything the product needs for one race, from `history` (races strictly before it) only:
    win odds, exact podium odds, and the fitted parameters so a browser can re-run what-ifs."""
    if len(history) < MIN_TRAIN:
        raise ValueError(f"need at least {MIN_TRAIN} earlier races, got {len(history)}")
    table = build_feature_table(history + [race])
    model = ScaledPL(MODEL_NAME, BASE_FEATURES).fit(history, table[:-1])
    rows = table[-1]
    u = model.utilities(rows)
    base = model.base
    idx = [FEATURES_INDEX[f] for f in BASE_FEATURES]
    return {
        "probs": model.predict(race, rows),
        "podium": model.podium_probs(u),
        "model": {"features": BASE_FEATURES, "mu": base.mu, "sd": base.sd, "w": base.w, "scales": model.scales},
        "features": {r[0]: [r[1][i] for i in idx] for r in rows},
    }


def forecast(history: list[Race], race: Race) -> dict[str, float]:
    """P(win) for each driver in `race`, using only `history` (races strictly before it)."""
    return forecast_detail(history, race)["probs"]


def entries_payload(race: Race, probs: dict[str, float], podium: dict[str, float] | None = None) -> list[dict]:
    rows = [
        {"driver_id": e.driver_id, "driver": e.driver, "team": e.team, "grid": e.grid,
         "p": round(probs[e.driver_id], 6),
         **({"podium": round(podium[e.driver_id], 6)} if podium else {})}
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
