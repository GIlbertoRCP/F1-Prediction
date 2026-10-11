import datetime as dt
import sys
import unittest
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import fetch_fastf1_grid as g  # noqa: E402

NAN = float("nan")


def rec(code, pos, q1=None, q2=None, q3=None):
    return {"Abbreviation": code, "Position": pos, "Q1": q1, "Q2": q2, "Q3": q3}


class FastF1GridTest(unittest.TestCase):
    sched = {"season": 2026, "round": 17, "race": "Singapore Grand Prix", "date": "2026-10-11", "circuit": "marina_bay",
             "quali_date": "2026-10-10", "quali_time": "13:00:00Z"}

    def test_lap_text(self):
        self.assertEqual(g.lap_text(timedelta(seconds=95.631)), "1:35.631")
        self.assertEqual(g.lap_text(timedelta(seconds=59.5)), "0:59.500")
        self.assertEqual(g.lap_text(None), "")
        self.assertEqual(g.lap_text(NAN), "")

    def test_due_rounds_waits_two_hours_and_skips_known(self):
        t0 = dt.datetime(2026, 10, 10, 14, 0, tzinfo=dt.timezone.utc)
        self.assertEqual(g.due_rounds([self.sched], set(), set(), t0), [])
        t1 = dt.datetime(2026, 10, 10, 15, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(len(g.due_rounds([self.sched], set(), set(), t1)), 1)
        self.assertEqual(g.due_rounds([self.sched], set(), {(2026, 17)}, t1), [])
        self.assertEqual(g.due_rounds([self.sched], {(2026, 17)}, set(), t1), [])

    def test_build_rows_orders_and_maps(self):
        codes = [f"D{i:02d}" for i in range(20)]
        known = {c: (f"id_{c}", f"team_{i // 2}") for i, c in enumerate(codes)}
        records = [rec(c, float(20 - i), timedelta(seconds=80 + i)) for i, c in enumerate(codes)]
        rows = g.build_rows(records, self.sched, known)
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["driver"], "D19")
        self.assertEqual([r["quali_position"] for r in rows], list(range(1, 21)))
        self.assertEqual(rows[0]["driver_id"], "id_D19")

    def test_refuses_unknown_driver_or_short_session(self):
        codes = [f"D{i:02d}" for i in range(20)]
        known = {c: (f"id_{c}", "t") for c in codes[:19]}
        records = [rec(c, float(i + 1)) for i, c in enumerate(codes)]
        self.assertEqual(g.build_rows(records, self.sched, known), [])
        self.assertEqual(g.build_rows(records[:10], self.sched, {c: (c, "t") for c in codes}), [])

    def test_nan_positions_go_last(self):
        codes = [f"D{i:02d}" for i in range(18)]
        known = {c: (c, "t") for c in codes}
        records = [rec(c, float(i + 1)) for i, c in enumerate(codes)]
        records[0]["Position"] = NAN
        rows = g.build_rows(records, self.sched, known)
        self.assertEqual(rows[-1]["driver"], "D00")


if __name__ == "__main__":
    unittest.main()
