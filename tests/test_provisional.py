import unittest
from pathlib import Path

from evaluation.data import load_races
from oracle import provisional

RESULTS = Path(__file__).resolve().parent.parent / "data" / "results"


class ProvisionalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.races = load_races(RESULTS)

    def test_form_stage_sums_to_one_and_has_no_grid(self):
        nxt = {"season": 2030, "round": 1, "race": "Test GP", "date": "2030-01-01", "sprint": ""}
        out = provisional.build(self.races, RESULTS, nxt)
        self.assertEqual(out["stage"], "form")
        self.assertAlmostEqual(sum(r["p"] for r in out["predictions"]), 1.0, places=3)
        self.assertTrue(all(r["grid"] is None for r in out["predictions"]))

    def test_recent_form_and_stages(self):
        nxt = {"season": 2030, "round": 1, "race": "Test GP", "date": "2030-01-01", "sprint": ""}
        out = provisional.build(self.races, RESULTS, nxt)
        self.assertEqual([s["key"] for s in out["stages"]], ["form", "quali"])   # no sprint step on a normal weekend
        last = self.races[-1]
        for row in out["predictions"]:
            self.assertLessEqual(len(row["recent"]), 5)
            e = next(e for e in last.entries if e.driver_id == row["driver_id"])
            self.assertEqual(row["recent"][-1], e.finish_position if e.classified else None)
        sprint = provisional.build(self.races, RESULTS, {**nxt, "sprint": "1"})
        self.assertIn("sprint", [s["key"] for s in sprint["stages"]])

    def test_sprint_stage_uses_sprint_order(self):
        # replay a real past sprint weekend: only earlier races are visible
        import csv
        with open(RESULTS / "sprints.csv") as f:
            first = next(csv.DictReader(f))
        key = (int(first["season"]), int(first["round"]))
        hist = [r for r in self.races if r.key < key]
        if len(hist) <= 15:
            self.skipTest("not enough history before the first sprint")
        later = [r for r in self.races if r.key >= key and r.season == key[0]]
        nxt = {"season": key[0], "round": key[1], "race": first["race"], "date": first["date"], "sprint": "1"}
        out = provisional.build(hist, RESULTS, nxt)
        self.assertEqual(out["stage"], "sprint")
        self.assertAlmostEqual(sum(r["p"] for r in out["predictions"]), 1.0, places=3)
        self.assertTrue(any(r["grid"] for r in out["predictions"]))

    def test_none_without_a_next_race(self):
        self.assertIsNone(provisional.build(self.races, RESULTS, None))


if __name__ == "__main__":
    unittest.main()
