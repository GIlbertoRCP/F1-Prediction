"""Download practice-session lap data from FastF1 and write pre-qualifying pace features.

Run this on a machine with internet (not in the sandbox). Lap timing only: no car telemetry, so it
is much lighter than a full session load. Resumable: weekends already in the CSV are skipped.

    uv run python scripts/extract_practice_features.py --from 2022 --to 2026 --limit 1   # smoke test
    uv run python scripts/extract_practice_features.py --from 2022 --to 2026             # everything

Only practice sessions that start before the weekend's Qualifying session are used.
"""
import argparse
import csv
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evaluation.practice import FIELDS, weekend_features  # noqa: E402

OUT = ROOT / "data" / "telemetry" / "practice_features.csv"
ERRORS = ROOT / "data" / "telemetry" / "errors.log"


def laps_to_records(laps) -> list[dict]:
    import pandas as pd
    recs = []
    for r in laps.itertuples(index=False):
        lt = r.LapTime
        recs.append({
            "driver": r.Driver, "team": getattr(r, "Team", ""),
            "lap_time": lt.total_seconds() if pd.notna(lt) else None,
            "compound": str(r.Compound) if pd.notna(r.Compound) else None,
            "stint": r.Stint if pd.notna(r.Stint) else None,
            "in_lap": pd.notna(r.PitInTime), "out_lap": pd.notna(r.PitOutTime),
            "track_clear": str(r.TrackStatus) == "1",
            "deleted": bool(getattr(r, "Deleted", False)) if pd.notna(getattr(r, "Deleted", None)) else False,
        })
    return recs


def weekend_sessions(event):
    """Practice sessions that start before Qualifying, as FastF1 session names."""
    import pandas as pd
    quali = None
    names = []
    for i in range(1, 6):
        name = event.get(f"Session{i}")
        date = event.get(f"Session{i}DateUtc")
        if not name or pd.isna(date):
            continue
        names.append((name, date))
        if name == "Qualifying":
            quali = date
    if quali is None:
        return []
    return [n for n, d in names if n.startswith("Practice") and d < quali]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=2022)
    ap.add_argument("--to", dest="end", type=int, default=2026)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many new weekends (smoke test)")
    args = ap.parse_args()
    import fastf1
    fastf1.Cache.enable_cache(str(ROOT / ".f1_cache")) if (ROOT / ".f1_cache").exists() else None
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if OUT.exists():
        with open(OUT, newline="") as f:
            done = {(int(r["season"]), int(r["round"])) for r in csv.DictReader(f)}
    new = 0
    write_header = not OUT.exists()
    with open(OUT, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            w.writeheader()
        for season in range(args.start, args.end + 1):
            schedule = fastf1.get_event_schedule(season, include_testing=False)
            for _, event in schedule.iterrows():
                rnd = int(event["RoundNumber"])
                if (season, rnd) in done:
                    continue
                if args.limit and new >= args.limit:
                    print(f"limit reached ({new} weekends)")
                    return
                label = f"{season} R{rnd} {event['EventName']}"
                try:
                    names = weekend_sessions(event)
                    sessions = []
                    for name in names:
                        s = fastf1.get_session(season, rnd, name)
                        s.load(laps=True, telemetry=False, weather=False, messages=False)
                        sessions.append(laps_to_records(s.laps))
                    feats = weekend_features(sessions)
                    for d, v in sorted(feats.items()):
                        w.writerow({"season": season, "round": rnd, "race": event["EventName"], "driver": d,
                                    "team": v["team"], "fp_gap": f"{v['fp_gap']:.4f}",
                                    "fp_long": "" if v["fp_long"] is None else f"{v['fp_long']:.4f}",
                                    "fp_sessions": v["fp_sessions"], "fp_laps": v["fp_laps"]})
                    f.flush()
                    new += 1
                    print(f"{label}: {len(feats)} drivers from {len(names)} practice sessions "
                          f"({', '.join(names) or 'none before qualifying'})")
                except Exception:   # a bad weekend must not stop a multi-hour run
                    print(f"{label}: FAILED (see {ERRORS.name})", file=sys.stderr)
                    with open(ERRORS, "a") as e:
                        e.write(f"{label}\n{traceback.format_exc()}\n")
    print(f"done: {new} new weekends")


if __name__ == "__main__":
    main()
