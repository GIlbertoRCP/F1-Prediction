import datetime as dt
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.data import Entry, Race, load_races
from evaluation import season as S
from oracle import championship as C
from oracle.schedule import parse_schedule

REAL = Path(__file__).resolve().parent.parent / "data" / "results"
PTS = S.RACE_POINTS


def toy_race(season, rnd, order, teams=None):
    """order: list of driver ids, first = winner; two drivers per team."""
    entries = []
    for pos, d in enumerate(order, 1):
        team = (teams or {}).get(d, "t" + str((pos - 1) // 2))
        entries.append(Entry(d.upper(), d, team, pos, pos, True, points=float(PTS[pos - 1]) if pos <= 10 else 0.0))
    return Race(season, rnd, f"R{rnd}", entries, f"{season}-01-{rnd:02d}")


def toy_history(n=20, ids=None):
    ids = ids or [f"d{i}" for i in range(10)]
    rng = random.Random(1)
    out = []
    for i in range(n):
        order = sorted(ids, key=lambda d: int(d[1:]) + rng.random() * 3)
        out.append(toy_race(2020 + i // 10, i % 10 + 1, order))
    return out


class StandingTests(unittest.TestCase):
    def test_sums_races_and_sprints_up_to_round(self):
        races = [toy_race(2024, 1, ["a", "b"]), toy_race(2024, 2, ["b", "a"]), toy_race(2023, 5, ["a", "b"])]
        sprints = {(2024, 2, "a"): (8.0, "t0"), (2024, 3, "a"): (8.0, "t0")}
        s = S.standing_after(races, sprints, 2024, 2)
        self.assertEqual(s.driver_points, {"a": 25 + 18 + 8, "b": 18 + 25})
        self.assertEqual(s.team_points["t0"], 25 + 18 + 18 + 25 + 8)

    def test_other_seasons_and_later_rounds_excluded(self):
        races = [toy_race(2024, 1, ["a", "b"]), toy_race(2024, 3, ["a", "b"])]
        self.assertEqual(S.standing_after(races, {}, 2024, 2).driver_points["a"], 25)


class SimulationTests(unittest.TestCase):
    def setUp(self):
        self.ids = ["a", "b", "c", "d"]
        self.teams = {"a": "x", "b": "x", "c": "y", "d": "y"}

    def run_sim(self, u, standing, remaining, **kw):
        return S.simulate_season(u, [1.0] * 10, self.teams, standing, remaining, 2024, n_sims=400, **kw)

    def test_points_added_per_race_match_the_scale(self):
        st = S.Standing()
        u = {d: 0.0 for d in self.ids}
        sim = self.run_sim(u, st, [{"round": 1, "sprint": False}], tau=0.0)
        # four drivers: only the top four places score; the total is always 25+18+15+12
        for i in range(400):
            self.assertAlmostEqual(sum(v[i] for v in sim["driver_final"].values()), 25 + 18 + 15 + 12)

    def test_sprint_adds_sprint_points(self):
        st = S.Standing()
        u = {d: 0.0 for d in self.ids}
        sim = self.run_sim(u, st, [{"round": 1, "sprint": True}], tau=0.0)
        total = sum(sim["driver_final"][d][0] for d in self.ids)
        self.assertEqual(total, 25 + 18 + 15 + 12 + 8 + 7 + 6 + 5)

    def test_runaway_leader_always_wins(self):
        st = S.Standing(driver_points={"a": 500.0, "b": 10.0, "c": 5.0, "d": 0.0},
                        team_points={"x": 510.0, "y": 5.0})
        u = {"a": 0.0, "b": 0.0, "c": 0.0, "d": 0.0}
        sim = self.run_sim(u, st, [{"round": r, "sprint": False} for r in range(1, 4)], tau=0.5)
        self.assertEqual(sim["driver_titles"]["a"], 400)
        self.assertEqual(sim["team_titles"]["x"], 400)

    def test_title_counts_sum_to_n(self):
        st = S.Standing()
        u = {"a": 1.0, "b": 0.5, "c": 0.0, "d": -0.5}
        sim = self.run_sim(u, st, [{"round": r, "sprint": False} for r in range(1, 6)], tau=0.3)
        self.assertEqual(sum(sim["driver_titles"].values()), 400)
        self.assertGreater(sim["driver_titles"]["a"], sim["driver_titles"]["d"])

    def test_deterministic_for_a_seed(self):
        st = S.Standing()
        u = {d: 0.0 for d in self.ids}
        rem = [{"round": 1, "sprint": False}]
        a = self.run_sim(u, st, rem, seed=5)
        b = self.run_sim(u, st, rem, seed=5)
        self.assertEqual(a["driver_final"], b["driver_final"])

    def test_driver_who_is_out_scores_nothing_more(self):
        st = S.Standing(driver_points={"a": 100.0})
        u = {d: 0.0 for d in self.ids}
        sim = self.run_sim(u, st, [{"round": 1, "sprint": False}] * 3, tau=0.0, out={"a"})
        self.assertEqual(set(sim["driver_final"]["a"]), {100.0})

    def test_season_scoring_scheme(self):
        self.assertEqual(S.sprint_scheme(2021), [3, 2, 1])
        self.assertEqual(S.sprint_scheme(2024), [8, 7, 6, 5, 4, 3, 2, 1])


class NoLookaheadTests(unittest.TestCase):
    def test_future_results_do_not_change_utilities(self):
        hist = toy_history(24)
        base = hist[:20]
        u1, s1 = S.fit_form_model(base, base[-1])
        # a different "future" must not matter: fit_form_model only ever sees `history`
        u2, s2 = S.fit_form_model(list(base), base[-1])
        self.assertEqual(u1, u2)
        self.assertEqual(s1, s2)

    def test_stronger_recent_form_gets_higher_utility(self):
        u, _ = S.fit_form_model(toy_history(24), toy_history(24)[-1])
        self.assertGreater(u["d0"], u["d9"])

    def test_points_features_use_only_earlier_races(self):
        hist = toy_history(18)
        table = S.points_form_table(hist)
        k = len(S.FEATURES)
        # first race: nothing to learn from, so every driver gets the same prior
        priors = {row[1][k] for row in table[0]}
        self.assertEqual(priors, {S.PTS_DEFAULT})
        # changing the last race's points must not change the last race's own features
        altered = list(hist)
        last = altered[-1]
        altered[-1] = Race(last.season, last.round, last.name,
                           [Entry(**{**e.__dict__, "points": 99.0}) for e in last.entries], last.date)
        self.assertEqual(S.points_form_table(altered)[-1], table[-1])

    def test_needs_enough_history(self):
        with self.assertRaises(ValueError):
            S.fit_form_model(toy_history(5), toy_history(5)[-1])


class CalendarTests(unittest.TestCase):
    def test_merges_played_and_scheduled_rounds(self):
        races = [toy_race(2026, 1, ["a", "b"]), toy_race(2026, 2, ["a", "b"]), toy_race(2026, 3, ["a", "b"])]
        sprints = {(2026, 2, "a"): (8.0, "t0")}
        schedule = [{"season": 2026, "round": 4, "race": "Four", "date": "2026-05-01", "sprint": "1"},
                    {"season": 2026, "round": 5, "race": "Five", "date": "2026-05-08", "sprint": ""},
                    {"season": 2026, "round": 3, "race": "Three", "date": "2026-04-01", "sprint": ""}]
        rem = C.remaining_calendar(races, sprints, schedule, 2026, 1)
        self.assertEqual([r["round"] for r in rem], [2, 3, 4, 5])
        self.assertEqual([r["sprint"] for r in rem], [True, False, True, False])

    def test_schedule_parser_reads_sprint_flag(self):
        payload = {"MRData": {"RaceTable": {"Races": [
            {"season": "2026", "round": "2", "raceName": "A", "Circuit": {"circuitId": "x"}, "date": "2026-03-15",
             "Sprint": {"date": "2026-03-14"}},
            {"season": "2026", "round": "3", "raceName": "B", "Circuit": {"circuitId": "y"}, "date": "2026-03-29"}]}}}
        rows = parse_schedule(payload)
        self.assertEqual([r["sprint"] for r in rows], ["1", ""])


class LiveLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.races = [r for r in load_races(REAL) if (r.season, r.round) <= (2026, 16)]
        self.sprints = C.load_sprint_points(REAL)
        self.schedule = [
            {"season": 2026, "round": 17, "race": "Singapore", "date": "2026-10-11", "sprint": "1"},
            {"season": 2026, "round": 18, "race": "USA", "date": "2026-10-25", "sprint": ""}]

    def freeze(self, day):
        now = dt.datetime(2026, 10, day, 12, tzinfo=dt.timezone.utc)
        return C.freeze_live(self.races, self.sprints, self.schedule, self.tmp, now, 2026, 16)

    def test_freezes_once_and_chain_verifies(self):
        self.assertIn("FROZE", self.freeze(8))
        self.assertIn("kept existing", self.freeze(9))
        summary = C.live_summary(self.tmp)
        self.assertEqual(summary["records"], 1)
        self.assertTrue(summary["chain_ok"])
        self.assertEqual(summary["log"][0]["after_round"], 16)
        self.assertTrue(0.0 <= summary["log"][0]["leader_title"] <= 1.0)

    def test_refuses_after_next_race(self):
        self.assertIn("SKIPPED", self.freeze(12))
        self.assertEqual(C.live_summary(self.tmp)["records"], 0)

    def test_tampering_breaks_chain(self):
        self.freeze(8)
        path = self.tmp / C.LIVE_FILE
        path.write_text(path.read_text().replace('"season":2026', '"season":2025', 1))
        self.assertFalse(C.live_summary(self.tmp)["chain_ok"])


class RealDataTests(unittest.TestCase):
    def test_title_odds_are_a_distribution(self):
        races = [r for r in load_races(REAL) if (r.season, r.round) <= (2026, 16)]
        sprints = C.load_sprint_points(REAL)
        rem = [{"round": 17, "sprint": True}, {"round": 18, "sprint": False}]
        fc = S.forecast_season(races, sprints, 2026, 16, rem, n_sims=300)
        self.assertAlmostEqual(sum(d["title"] for d in fc["drivers"]), 1.0, places=6)
        self.assertAlmostEqual(sum(t["title"] for t in fc["teams"]), 1.0, places=6)
        for d in fc["drivers"]:
            self.assertLessEqual(d["p10"], d["p90"])
            self.assertGreaterEqual(d["mean"], d["points"] - 1e-9)

    def test_known_2025_standing_after_round_24(self):
        races = load_races(REAL)
        s = S.standing_after(races, C.load_sprint_points(REAL), 2025, 24)
        self.assertEqual(s.driver_points["norris"], 423)
        self.assertEqual(s.team_points["mclaren"], 833)


if __name__ == "__main__":
    unittest.main()
