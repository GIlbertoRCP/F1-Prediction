"""Preview the site in states it has not reached yet: season end, the off-season and the next season's first
rounds. Copies the real data, adds made-up results (the last race repeated) and next year's calendar (this
year's, a year later), and runs the publisher with a pretend clock. Nothing in the repo is touched.

    python3 scripts/dry_run_season.py /tmp/dry      # then serve /tmp/dry and open <scenario>/site/

The seasons and dates below are for the 2026 -> 2027 rollover; change them for a later one.
"""
import csv, datetime as dt, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1])

def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))

def write(p, data):
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0].keys())); w.writeheader(); w.writerows(data)

def copy_round(data, src, dst):
    """Rows of (season, round) `src` relabelled as schedule row `dst`."""
    return [{**r, "season": dst["season"], "round": dst["round"], "race": dst["race"], "date": dst["date"], "circuit": dst["circuit"]}
            for r in data if (r["season"], r["round"]) == src]

def scenario(name, now, end_2026=True, cal_2027=False, r1_2027=False):
    d = OUT / name
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(ROOT / "data" / "results", d / "results")
    shutil.copytree(ROOT / "data" / "predictions", d / "predictions")
    shutil.copytree(ROOT / "site", d / "site", ignore=shutil.ignore_patterns("data"))
    sched = rows(d / "results" / "schedule.csv")
    if cal_2027:
        extra = []
        for r in [r for r in sched if r["season"] == "2026"]:
            shift = lambda x: (dt.date.fromisoformat(x) + dt.timedelta(days=364)).isoformat() if x else x
            extra.append({**r, "season": "2027", "date": shift(r["date"]), "quali_date": shift(r["quali_date"])})
        sched += extra
        write(d / "results" / "schedule.csv", sched)
    by = {(r["season"], r["round"]): r for r in sched}
    for fn in ("races.csv", "qualifying.csv"):
        data = rows(d / "results" / fn)
        if end_2026:
            for rnd in ("21", "22", "23"):
                data += copy_round(data, ("2026", "20"), by[("2026", rnd)])
        if r1_2027:
            data += copy_round(data, ("2026", "1"), by[("2027", "1")])
        write(d / "results" / fn, data)
    (d / "site" / "data").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "site" / "data" / "circuits.json", d / "site" / "data" / "circuits.json")
    r = subprocess.run([sys.executable, "-m", "oracle.publish", "--results-dir", d / "results", "--predictions-dir", d / "predictions",
                        "--out", d / "site", "--now", now], cwd=ROOT, capture_output=True, text=True)
    print(f"== {name} (now {now}) exit {r.returncode}\n{r.stdout[-600:]}{r.stderr[-1500:]}")

if __name__ == "__main__":
    scenario("a-season-end", "2026-12-08T12:00:00")
    scenario("b-january", "2027-01-15T12:00:00", cal_2027=True)
    scenario("c-2027-r1-week", "2027-03-04T12:00:00", cal_2027=True)
    scenario("d-after-2027-r1", "2027-03-10T12:00:00", cal_2027=True, r1_2027=True)
