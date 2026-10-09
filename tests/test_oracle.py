import csv
import datetime as dt
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.data import load_races
from oracle import engine, store
from oracle.schedule import next_race, parse_schedule
from oracle.publish import backfill_backtest, freeze_live
from oracle.service import LIVE_FILE, build_bundle

REAL = Path(__file__).resolve().parent.parent / "data" / "results"
BEFORE_R16 = dt.datetime(2026, 10, 3, 12, tzinfo=dt.timezone.utc)
AFTER_R16 = dt.datetime(2026, 10, 8, 12, tzinfo=dt.timezone.utc)


def record(rnd, p=0.5):
    return {"season": 2030, "round": rnd, "race": "X", "date": "2030-01-01", "kind": "live",
            "predictions": [{"driver_id": "a", "p": p}, {"driver_id": "b", "p": 1 - p}]}


class LogTests(unittest.TestCase):
    def test_chain_detects_edits_and_refuses_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "live.jsonl"
            self.assertTrue(store.append_live(path, record(1)))
            self.assertTrue(store.append_live(path, record(2)))
            self.assertFalse(store.append_live(path, record(2, p=0.9)))      # no overwrite
            self.assertTrue(store.verify_chain(store.read_log(path))[0])
            path.write_text(path.read_text().replace("0.5", "0.6", 1))        # tamper with record 1
            ok, msg = store.verify_chain(store.read_log(path))
            self.assertFalse(ok)
            with self.assertRaises(RuntimeError):
                store.append_live(path, record(3))

    def test_deleting_a_record_breaks_the_chain(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "live.jsonl"
            for i in (1, 2, 3):
                store.append_live(path, record(i))
            lines = path.read_text().splitlines()
            path.write_text("\n".join([lines[0], lines[2]]) + "\n")
            self.assertFalse(store.verify_chain(store.read_log(path))[0])


class LiveFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tmp = Path(self.tmp.name)
        self.pre = tmp / "pre"          # data as it was after qualifying for R16, before the race
        self.pre.mkdir()
        shutil.copy(REAL / "qualifying.csv", self.pre)
        with open(REAL / "races.csv", newline="") as f, open(self.pre / "races.csv", "w", newline="") as g:
            rd = csv.DictReader(f)
            w = csv.DictWriter(g, fieldnames=rd.fieldnames)
            w.writeheader()
            w.writerows(r for r in rd if not (r["season"] == "2026" and r["round"] == "16"))
        self.pred = tmp / "pred"

    def test_freeze_uses_only_earlier_races_and_never_overwrites(self):
        races = load_races(self.pre)
        self.assertEqual(races[-1].key, (2026, 15))
        msgs = freeze_live(races, self.pre, self.pred, BEFORE_R16)
        self.assertTrue(msgs[0].startswith("FROZE"), msgs)
        rec = store.read_log(self.pred / LIVE_FILE)[0]
        self.assertEqual((rec["season"], rec["round"]), (2026, 16))
        self.assertAlmostEqual(sum(p["p"] for p in rec["predictions"]), 1.0, places=4)
        self.assertEqual(rec["train_races"], len(races))
        self.assertEqual(rec["made_at"], BEFORE_R16.isoformat(timespec="seconds"))
        again = freeze_live(races, self.pre, self.pred, BEFORE_R16)
        self.assertTrue(again[0].startswith("kept existing"))
        self.assertEqual(len(store.read_log(self.pred / LIVE_FILE)), 1)

    def test_refuses_to_log_after_the_race(self):
        races = load_races(self.pre)
        msgs = freeze_live(races, self.pre, self.pred, AFTER_R16)
        self.assertTrue(msgs[0].startswith("SKIPPED"), msgs)
        self.assertEqual(store.read_log(self.pred / LIVE_FILE), [])

    def test_lifecycle_open_then_settled(self):
        races = load_races(self.pre)
        freeze_live(races, self.pre, self.pred, BEFORE_R16)
        open_bundle = build_bundle(self.pre, self.pred, BEFORE_R16)
        self.assertEqual(open_bundle["forecast"]["status"], "open")
        self.assertEqual(open_bundle["track_record"]["live"]["n"], 0)
        done = build_bundle(REAL, self.pred, AFTER_R16)          # results now exist
        self.assertEqual(done["forecast"]["status"], "none")
        live = done["track_record"]["live"]
        self.assertEqual(live["n"], 1)
        self.assertEqual(done["races"]["2026-16"]["kind"], "live")
        self.assertTrue(done["meta"]["live_log"]["chain_ok"])

    def test_forecast_ignores_the_race_result(self):
        """Forecast for R16 must be identical whether or not R16's own result is in the history."""
        pre = load_races(self.pre)
        full = load_races(REAL)
        race_pre = engine.load_pending(self.pre, pre)[0]
        p1 = engine.forecast(pre, race_pre)
        p2 = engine.forecast(full[:-1], race_pre)
        for d in p1:
            self.assertAlmostEqual(p1[d], p2[d], places=12)


class ScheduleTests(unittest.TestCase):
    def test_parse_and_next_race(self):
        payload = {"MRData": {"RaceTable": {"Races": [
            {"season": "2026", "round": "17", "raceName": "A GP", "date": "2026-10-18", "time": "14:00:00Z",
             "Circuit": {"circuitId": "a"}, "Qualifying": {"date": "2026-10-17", "time": "14:00:00Z"}},
            {"season": "2026", "round": "18", "raceName": "B GP", "date": "2026-10-25",
             "Circuit": {"circuitId": "b"}},
        ]}}}
        rows = parse_schedule(payload)
        self.assertEqual(rows[0]["quali_date"], "2026-10-17")
        self.assertEqual(next_race(rows, "2026-10-08")["race"], "A GP")
        self.assertEqual(next_race(rows, "2026-10-19")["race"], "B GP")
        self.assertIsNone(next_race(rows, "2026-11-01"))


class BacktestTests(unittest.TestCase):
    def test_backfill_is_idempotent_and_matches_walkforward(self):
        races = load_races(REAL)[:40]
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(backfill_backtest(races, Path(d)), 25)
            self.assertEqual(backfill_backtest(races, Path(d)), 0)
            recs = store.read_log(Path(d) / "backtest.jsonl")
            self.assertEqual(len(recs), 25)
            i = 30
            probs = engine.forecast(races[:i], races[i])
            rec = next(r for r in recs if (r["season"], r["round"]) == races[i].key)
            for p in rec["predictions"]:
                self.assertAlmostEqual(p["p"], probs[p["driver_id"]], places=5)


if __name__ == "__main__":
    unittest.main()
