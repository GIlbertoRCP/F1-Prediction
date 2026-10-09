"""HTTP API and static site.  Run:  uvicorn oracle.api:app --port 8000

The API reads the same data the static site uses, rebuilt whenever the underlying files change.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .service import BACKTEST_FILE, LIVE_FILE, build_bundle

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = Path(os.environ.get("ORACLE_RESULTS_DIR", ROOT / "data" / "results"))
PRED_DIR = Path(os.environ.get("ORACLE_PREDICTIONS_DIR", ROOT / "data" / "predictions"))
SITE_DIR = Path(os.environ.get("ORACLE_SITE_DIR", ROOT / "site"))

app = FastAPI(title="F1 Winner Oracle", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])

_cache: dict = {"stamp": None, "bundle": None}


def _stamp():
    files = [RESULTS_DIR / "races.csv", RESULTS_DIR / "qualifying.csv", RESULTS_DIR / "schedule.csv",
             PRED_DIR / LIVE_FILE, PRED_DIR / BACKTEST_FILE]
    return tuple(f.stat().st_mtime_ns if f.exists() else None for f in files)


def bundle() -> dict:
    stamp = _stamp()
    if _cache["stamp"] != stamp:
        _cache["bundle"] = build_bundle(RESULTS_DIR, PRED_DIR)
        _cache["stamp"] = stamp
    return _cache["bundle"]


@app.get("/api/health")
def health():
    meta = bundle()["meta"]
    return {"ok": meta["live_log"]["chain_ok"], **meta}


@app.get("/api/forecast")
def forecast():
    """The open forecast for the upcoming race, or {status: 'none'} between qualifying sessions."""
    return bundle()["forecast"]


@app.get("/api/track-record")
def track_record():
    return bundle()["track_record"]


@app.get("/api/races")
def races():
    pages = bundle()["races"].values()
    return sorted(({"season": p["season"], "round": p["round"], "race": p["race"], "date": p["date"],
                    "kind": p["kind"]} for p in pages), key=lambda r: (r["season"], r["round"]), reverse=True)


@app.get("/api/races/{season}/{round}")
def race(season: int, round: int):
    page = bundle()["races"].get(f"{season}-{round}")
    if not page:
        raise HTTPException(404, "no forecast for that race")
    return page


if SITE_DIR.exists():
    app.mount("/", StaticFiles(directory=SITE_DIR, html=True), name="site")
