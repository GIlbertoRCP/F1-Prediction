"""Draw every circuit from real car positions: one fast qualifying lap per circuit, from FastF1.

Run this on a machine with internet (not in the sandbox). Resumable: circuits already in
site/data/circuits.json are skipped. Waits and retries when FastF1's hourly API limit is hit.

    uv run python scripts/extract_circuits.py --limit 1     # smoke test
    uv run python scripts/extract_circuits.py               # every circuit in the results

Uses the most recent season each circuit was raced; falls back to earlier seasons if one is unavailable.
"""
import argparse
import json
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evaluation.jolpica import read_rows  # noqa: E402
from oracle.circuits import outline  # noqa: E402

OUT = ROOT / "site" / "data" / "circuits.json"
ERRORS = ROOT / "data" / "telemetry" / "circuit_errors.log"
RATE_LIMIT_WAIT = 600
FIRST_SEASON = 2018        # FastF1 has no position data before this


def occurrences(results_dir: Path) -> dict[str, list[tuple[int, int]]]:
    seen: dict[str, set[tuple[int, int]]] = {}
    for r in read_rows(results_dir / "races.csv"):
        if r["season"] >= FIRST_SEASON and r.get("circuit"):
            seen.setdefault(r["circuit"], set()).add((r["season"], r["round"]))
    return {c: sorted(v, reverse=True) for c, v in seen.items()}


def lap_outline(season: int, rnd: int) -> dict:
    import fastf1
    s = fastf1.get_session(season, rnd, "Qualifying")
    s.load(laps=True, telemetry=True, weather=False, messages=False)
    tel = s.laps.pick_fastest().get_telemetry()
    rotation = 0.0
    try:
        rotation = float(s.get_circuit_info().rotation)
    except Exception:
        pass
    return {**outline(list(tel["X"]), list(tel["Y"]), rotation), "season": season}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    import fastf1
    if (ROOT / ".f1_cache").exists():
        fastf1.Cache.enable_cache(str(ROOT / ".f1_cache"))
    data = json.loads(OUT.read_text()) if OUT.exists() else {}
    new = 0
    for circuit, rounds in sorted(occurrences(ROOT / "data" / "results").items()):
        if circuit in data:
            continue
        if args.limit and new >= args.limit:
            break
        for season, rnd in rounds[:3]:                    # newest first; try up to three seasons
            while True:
                try:
                    data[circuit] = lap_outline(season, rnd)
                    OUT.parent.mkdir(parents=True, exist_ok=True)
                    OUT.write_text(json.dumps(data, separators=(",", ":")))
                    new += 1
                    print(f"{circuit}: drawn from {season} R{rnd}")
                    break
                except Exception as exc:
                    if "RateLimit" in type(exc).__name__:
                        print(f"{circuit}: API rate limit reached, waiting {RATE_LIMIT_WAIT // 60} min", flush=True)
                        time.sleep(RATE_LIMIT_WAIT)
                        continue
                    print(f"{circuit}: {season} R{rnd} failed (see {ERRORS.name})", file=sys.stderr)
                    ERRORS.parent.mkdir(parents=True, exist_ok=True)
                    with open(ERRORS, "a") as f:
                        f.write(f"{circuit} {season} R{rnd}\n{traceback.format_exc()}\n")
                    break
            if circuit in data:
                break
    print(f"done: {new} new circuits, {len(data)} total")


if __name__ == "__main__":
    main()
