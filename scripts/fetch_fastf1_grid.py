"""Fallback for the starting grid: read qualifying from F1's own timing data (FastF1) when the Jolpica API is late.

Run after scripts/fetch_results.py. It only acts when ALL of these hold:
  * a race on the calendar has had its qualifying session finish (calendar time + 2 hours),
  * the race itself has not been run,
  * qualifying.csv has no rows for it yet (Jolpica is late).
It then writes that round's qualifying rows in the same format Jolpica rows use. The next fetch_results.py run
replaces the whole season from Jolpica, so the official rows win as soon as they exist.

Driver and team ids are copied from the same driver's rows in the latest race, so they match everywhere else.
It never guesses: if the session is incomplete (fewer than 18 drivers) or a driver cannot be matched, it writes nothing.
"""
from __future__ import annotations

import datetime as dt
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evaluation.jolpica import dedupe, read_rows, write_rows  # noqa: E402
from oracle.schedule import read_schedule  # noqa: E402

OUT_DIR = ROOT / "data" / "results"
MIN_DRIVERS = 18
WAIT_AFTER_START = dt.timedelta(hours=2)


def due_rounds(schedule: list[dict], finished: set, have_quali: set, now: dt.datetime) -> list[dict]:
    """Calendar rows whose qualifying is over, with no race result and no qualifying rows yet."""
    out = []
    for r in schedule:
        key = (r["season"], r["round"])
        if key in finished or key in have_quali or not r.get("quali_date"):
            continue
        t = (r.get("quali_time") or "00:00:00Z").rstrip("Z")
        start = dt.datetime.fromisoformat(f"{r['quali_date']}T{t}+00:00")
        if now >= start + WAIT_AFTER_START and r["date"] >= (now - dt.timedelta(days=1)).date().isoformat():
            out.append(r)
    return sorted(out, key=lambda r: (r["season"], r["round"]))


def lap_text(value) -> str:
    """Timedelta (or NaT / None) -> '1:23.456', or '' when there was no time."""
    if value is None or value != value:
        return ""
    secs = value.total_seconds()
    if secs <= 0:
        return ""
    m, s = divmod(secs, 60)
    return f"{int(m)}:{s:06.3f}"


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return "_".join(text.replace("-", " ").split())


def build_rows(records: list[dict], sched: dict, known: dict[str, tuple[str, str]]) -> list[dict]:
    """records: FastF1 result rows as dicts. known: driver code -> (driver_id, team) from the latest race.

    Returns Jolpica-format rows, or [] if the session looks incomplete or a driver can't be matched."""
    classified = [r for r in records if r.get("Abbreviation")]
    if len(classified) < MIN_DRIVERS:
        return []
    ordered = sorted(classified, key=lambda r: (r.get("Position") is None or r["Position"] != r["Position"],
                                                r.get("Position") or 0))
    rows = []
    for i, r in enumerate(ordered, start=1):
        code = r["Abbreviation"]
        hit = known.get(code)
        if hit is None:      # a code that differs between the sources: fall back to the surname
            last = _slug(str(r.get("LastName") or ""))
            hit = next((v for k, v in known.items() if last and (v[0] == last or v[0].endswith("_" + last))), None)
        if hit is None:
            print(f"cannot match driver {code}; not writing the grid", file=sys.stderr)
            return []
        did, team = hit
        rows.append({
            "season": sched["season"], "round": sched["round"], "race": sched["race"], "date": sched["date"],
            "circuit": sched["circuit"], "driver": code, "driver_id": did, "team": team,
            "quali_position": i, "q1": lap_text(r.get("Q1")), "q2": lap_text(r.get("Q2")),
            "q3": lap_text(r.get("Q3")),
        })
    return rows


def known_drivers(race_rows: list[dict], season: int) -> dict[str, tuple[str, str]]:
    latest = max((r["round"] for r in race_rows if r["season"] == season), default=None)
    return {r["driver"]: (r["driver_id"], r["team"]) for r in race_rows
            if r["season"] == season and r["round"] == latest}


def main() -> int:
    now = dt.datetime.now(dt.timezone.utc)
    schedule = read_schedule(OUT_DIR / "schedule.csv")
    races = read_rows(OUT_DIR / "races.csv")
    quali = read_rows(OUT_DIR / "qualifying.csv")
    finished = {(r["season"], r["round"]) for r in races}
    have = {(r["season"], r["round"]) for r in quali}
    todo = due_rounds(schedule, finished, have, now)
    if not todo:
        print("fastf1 fallback: nothing to do")
        return 0
    import fastf1
    fastf1.Cache.enable_cache(str(_cache_dir()))
    added = []
    for sched in todo:
        known = known_drivers(races, sched["season"])
        try:
            ses = fastf1.get_session(sched["season"], sched["round"], "Q")
            ses.load(laps=False, telemetry=False, weather=False, messages=False)
            records = ses.results.to_dict("records")
        except Exception as exc:
            print(f"fastf1: {sched['season']} R{sched['round']} not available yet ({exc})")
            continue
        rows = build_rows(records, sched, known)
        if not rows:
            print(f"fastf1: {sched['season']} R{sched['round']} incomplete; nothing written")
            continue
        added.extend(rows)
        print(f"fastf1: wrote qualifying for {sched['season']} R{sched['round']} {sched['race']} ({len(rows)} drivers, "
              f"pole {rows[0]['driver']}); Jolpica rows replace these when published")
    if added:
        write_rows(OUT_DIR, "qualifying", dedupe(quali + added))
    return 0


def _cache_dir() -> Path:
    p = ROOT / ".f1_cache"
    p.mkdir(exist_ok=True)
    return p


if __name__ == "__main__":
    sys.exit(main())
