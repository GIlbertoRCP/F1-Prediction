"""Download full race / qualifying / sprint results from the Jolpica (Ergast-compatible) API.

Needs internet but no third-party packages. Writes data/results/{races,qualifying,sprints}.csv,
replacing the rows for the seasons fetched and keeping rows for other seasons.

Usage:
    python3 scripts/fetch_results.py                 # 2018 through current year
    python3 scripts/fetch_results.py --from 2014 --to 2026

Be polite: the public API rate-limits, so requests are spaced out and retried on 429.
"""
import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evaluation.jolpica import FILENAMES, dedupe, parse_payload, read_rows, write_rows  # noqa: E402
from oracle.schedule import parse_schedule, read_schedule, write_schedule  # noqa: E402

BASE = "https://api.jolpi.ca/ergast/f1"
OUT_DIR = ROOT / "data" / "results"
PAGE = 100
PAUSE = 0.7


def get_json(url: str, retries: int = 6) -> dict:
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"User-Agent": "f1-oracle-research/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = float(e.headers.get("Retry-After", delay))
                print(f"  HTTP {e.code}; retrying in {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                delay *= 2
                continue
            raise
        except urllib.error.URLError:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def fetch_season(season: int, kind: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        payload = get_json(f"{BASE}/{season}/{kind}.json?limit={PAGE}&offset={offset}")
        rows.extend(parse_payload(kind, payload))
        total = int(payload["MRData"]["total"])
        offset += PAGE
        time.sleep(PAUSE)
        if offset >= total:
            return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=2018)
    ap.add_argument("--to", dest="end", type=int, default=datetime.date.today().year)
    args = ap.parse_args()
    seasons = list(range(args.start, args.end + 1))

    for kind in ("results", "qualifying", "sprint"):
        fetched: list[dict] = []
        for season in seasons:
            rows = fetch_season(season, kind)
            print(f"{kind} {season}: {len(rows)} rows")
            fetched.extend(rows)
        existing = [r for r in read_rows(OUT_DIR / FILENAMES[kind]) if r["season"] not in seasons]
        merged = dedupe(existing + fetched)
        if merged:
            print(f"-> {write_rows(OUT_DIR, kind, merged).relative_to(ROOT)} ({len(merged)} rows)")
    fetch_schedule(seasons)


def fetch_schedule(seasons: list[int]) -> None:
    rows = []
    for season in seasons:
        rows.extend(parse_schedule(get_json(f"{BASE}/{season}.json?limit={PAGE}")))
        time.sleep(PAUSE)
    existing = [r for r in read_schedule(OUT_DIR / "schedule.csv") if r["season"] not in seasons]
    write_schedule(OUT_DIR / "schedule.csv", existing + rows)
    print(f"-> data/results/schedule.csv ({len(existing) + len(rows)} races)")


if __name__ == "__main__":
    main()
