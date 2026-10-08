import copy
import json
import math
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.data import Entry, Race, coverage
from evaluation.jolpica import parse_payload
from evaluation.metrics import bootstrap_ci, calibration_table, score_race
from evaluation.models import ConditionalLogit, FEATURES, GridPrior, build_feature_table, default_models
from evaluation.ranker import RankerModel, fit_beta, zscores
from evaluation.run import evaluate_scored, load_scores
from evaluation.walkforward import walk_forward


def make_races(n_races=40, n_drivers=10, seed=1, pole_wins=0.6):
    """Synthetic championship: the pole sitter wins `pole_wins` of the time; team 'a' is strongest."""
    rng = random.Random(seed)
    races = []
    for i in range(n_races):
        order = list(range(n_drivers))
        rng.shuffle(order)  # grid slot -> driver index
        winner_slot = 0 if rng.random() < pole_wins else rng.randrange(1, n_drivers)
        finish = list(range(n_drivers))
        finish.remove(winner_slot)
        rng.shuffle(finish)
        finish = [winner_slot] + finish  # finish order as grid slots
        entries = []
        for slot in range(n_drivers):
            d = order[slot]
            entries.append(Entry(f"D{d}", f"driver{d}", f"team{d // 2}", slot + 1,
                                 finish.index(slot) + 1, True))
        races.append(Race(2024 + i // 20, i % 20 + 1, f"R{i}", entries))
    return races


class ParseTests(unittest.TestCase):
    def test_parse_results_payload(self):
        payload = {"MRData": {"RaceTable": {"Races": [{
            "season": "2024", "round": "5", "raceName": "Miami Grand Prix", "date": "2024-05-05",
            "Circuit": {"circuitId": "miami"},
            "Results": [
                {"position": "1", "positionText": "1", "grid": "1", "Driver": {"code": "NOR", "driverId": "norris"},
                 "Constructor": {"constructorId": "mclaren"}, "status": "Finished", "points": "25"},
                {"position": "19", "positionText": "R", "grid": "0", "Driver": {"driverId": "x"},
                 "Constructor": {"constructorId": "haas"}, "status": "Engine", "points": "0"},
            ]}]}}}
        rows = parse_payload("results", payload)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["driver"], "NOR")
        self.assertEqual(rows[0]["finish_position"], 1)
        self.assertEqual(rows[1]["classified"], 0)       # 'R' = retired, not classified
        self.assertEqual(rows[1]["finish_position"], "")
        self.assertEqual(rows[1]["driver"], "x")         # falls back to driverId when no code


class MetricTests(unittest.TestCase):
    def test_uniform_logloss_and_brier(self):
        probs = {f"d{i}": 0.25 for i in range(4)}
        s = score_race((2024, 1), probs, "d2")
        self.assertAlmostEqual(s.logloss, math.log(4))
        self.assertAlmostEqual(s.brier, 3 * 0.25 ** 2 + 0.75 ** 2)

    def test_rank_and_tiebreak(self):
        s = score_race((2024, 1), {"a": 0.5, "b": 0.3, "c": 0.2}, "c")
        self.assertEqual((s.rank, s.top1, s.top3), (3, False, True))
        tie = score_race((2024, 1), {"a": 0.5, "b": 0.5}, "b")
        self.assertFalse(tie.top1)  # exact ties fall back to driver id, never to grid order

    def test_probs_are_normalised(self):
        s = score_race((2024, 1), {"a": 2.0, "b": 2.0}, "a")
        self.assertAlmostEqual(s.p_winner, 0.5)

    def test_bootstrap_is_deterministic_and_brackets_mean(self):
        vals = [0.0, 1.0] * 20
        lo, hi = bootstrap_ci(vals, seed=3)
        self.assertEqual((lo, hi), bootstrap_ci(vals, seed=3))
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)

    def test_calibration_counts_all_driver_races(self):
        scores = [score_race((2024, i), {"a": 0.7, "b": 0.3}, "a") for i in range(10)]
        table = calibration_table(scores)
        self.assertEqual(sum(r[2] for r in table), 20)


class NoLeakageTests(unittest.TestCase):
    """Predictions for race t must not depend on race t's result or any later race."""

    def predict_at(self, races, t):
        table = build_feature_table(races)
        out = {}
        for m in default_models():
            m.fit(races[:t], table[:t])
            out[m.name] = m.predict(races[t], table[t])
        return out

    def test_future_and_own_results_do_not_change_prediction(self):
        races = make_races()
        t = 25
        base = self.predict_at(races, t)
        altered = copy.deepcopy(races)
        # rewrite the target race's own result and every later result
        for race in altered[t:]:
            n = len(race.entries)
            race.entries = [Entry(e.driver, e.driver_id, e.team, e.grid,
                                  n - e.finish_position + 1, True) for e in race.entries]
        changed = self.predict_at(altered, t)
        for name in base:
            for d, p in base[name].items():
                self.assertAlmostEqual(p, changed[name][d], places=12, msg=f"{name} leaked for {d}")

    def test_features_use_only_strictly_earlier_races(self):
        races = make_races(n_races=6)
        table = build_feature_table(races)
        # first race: no history -> neutral defaults for every form feature
        for _, feats, _ in table[0]:
            self.assertEqual(feats[1:3], [0.5, 0.5])
            self.assertEqual(feats[3:], [0.0, 0.0])


class ModelTests(unittest.TestCase):
    def test_grid_prior_learns_pole_advantage(self):
        races = make_races(n_races=60, pole_wins=0.8, seed=2)
        m = GridPrior().fit(races, None)
        probs = m.predict(races[0], None)
        pole = next(e.driver_id for e in races[0].entries if e.grid == 1)
        self.assertEqual(max(probs, key=probs.get), pole)
        self.assertAlmostEqual(sum(probs.values()), 1.0)

    def test_logit_learns_negative_grid_weight(self):
        races = make_races(n_races=80, pole_wins=0.7, seed=4)
        table = build_feature_table(races)
        m = ConditionalLogit("t", FEATURES).fit(races, table)
        self.assertLess(m.w[FEATURES.index("log_grid")], -0.2)

    def test_logit_fit_actually_maximises_likelihood(self):
        """Regression: an unguarded Newton solver once diverged to a likelihood worse than w=0."""
        races = make_races(n_races=60, pole_wins=0.6, seed=7)
        table = build_feature_table(races)
        m = ConditionalLogit("t", FEATURES).fit(races, table)
        groups = [rows for rows in table if any(r[2] for r in rows)]
        Z = [([m._x(r[1]) for r in rows], [r[2] for r in rows].index(True)) for rows in groups]
        f = lambda w: m._penalised_loglik(Z, w)
        self.assertGreater(f(m.w), f([0.0] * len(m.w)))
        for j in range(len(m.w)):          # gradient is ~0 at the optimum
            up, dn = m.w[:], m.w[:]
            up[j] += 1e-5
            dn[j] -= 1e-5
            self.assertAlmostEqual((f(up) - f(dn)) / 2e-5, 0.0, places=3)

    def test_uniform_model_gets_no_credit_from_grid_order(self):
        races = make_races(n_races=40, pole_wins=0.9)
        res = walk_forward(races, [default_models()[0]], min_train=10)
        hit = sum(s.top1 for s in res["uniform"]) / len(res["uniform"])
        self.assertLess(hit, 0.5)   # pole wins 90% here, so a hidden grid tie-break would score ~0.9

    def test_walk_forward_covers_expected_races(self):
        races = make_races(n_races=30)
        res = walk_forward(races, default_models(), min_train=10)
        for name, scores in res.items():
            self.assertEqual(len(scores), 20, name)

    def test_coverage_reports_gaps(self):
        races = make_races(n_races=20)
        del races[2]
        self.assertEqual(coverage(races)[2024][1], [3])


class ExternalPredictionTests(unittest.TestCase):
    def test_scoring_an_external_model_csv(self):
        import csv
        import tempfile
        from evaluation.run import load_external

        races = make_races(n_races=30, pole_wins=0.8)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "oracle.csv"
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["season", "round", "driver_id", "win_prob"])
                for r in races:
                    for e in r.entries:                       # an "oracle" that always backs the pole sitter
                        w.writerow([r.season, r.round, e.driver_id, 0.9 if e.grid == 1 else 0.1 / 9])
            ext = load_external(path, races)
        res = walk_forward(races, default_models(), min_train=10, external=ext)
        self.assertEqual(len(res["oracle"]), 20)
        self.assertEqual(len(res["uniform"]), 20)            # all models scored on the same races
        pole_hit = sum(s.top1 for s in res["oracle"]) / 20
        self.assertGreater(pole_hit, 0.5)



def make_scores(races, informative: bool, seed=3):
    """Synthetic ranker output per race: informative scores favour the true winner, otherwise pure noise."""
    rng = random.Random(seed)
    out = {}
    for r in races:
        out[r.key] = {
            e.driver_id: rng.gauss(0, 1) + (2.5 if informative and e.driver_id == r.winner_id else 0.0)
            for e in r.entries
        }
    return out


class RankerTests(unittest.TestCase):
    def test_zscores_fill_missing_with_worst(self):
        z = zscores({"a": 3.0, "b": 1.0, "c": 2.0}, ["a", "b", "c", "d"])
        self.assertAlmostEqual(sum(z[:3]), 0.0)
        self.assertEqual(z[3], min(z[:3]))

    def test_fit_beta_recovers_positive_signal_and_shrinks_noise(self):
        races = make_races(n_races=80, pole_wins=0.4, seed=11)
        for informative, check in ((True, lambda b: b > 0.8), (False, lambda b: abs(b) < 0.5)):
            sc = make_scores(races, informative)
            groups = []
            for r in races:
                drivers = [e.driver_id for e in r.entries]
                groups.append(([0.0] * len(drivers), zscores(sc[r.key], drivers), drivers.index(r.winner_id)))
            self.assertTrue(check(fit_beta(groups)), f"informative={informative}")

    def test_stacked_model_improves_when_scores_informative_and_does_no_harm_when_noise(self):
        races = make_races(n_races=70, pole_wins=0.5, seed=5)
        table = build_feature_table(races)
        for informative in (True, False):
            res, betas = evaluate_scored(races, table, make_scores(races, informative), min_scored=20)
            base = sum(s.logloss for s in res["grid_plus_form"]) / len(res["grid_plus_form"])
            stacked = sum(s.logloss for s in res["grid_form_plus_ranker"]) / len(res["grid_form_plus_ranker"])
            if informative:
                self.assertLess(stacked, base - 0.3)
            else:
                self.assertLess(stacked, base + 0.1)   # shrinkage keeps noise from hurting much

    def test_ranker_predictions_do_not_leak_the_future(self):
        races = make_races(n_races=45, seed=9)
        sc = make_scores(races, informative=True)
        t = 35

        def predict(rs, scores):
            tb = build_feature_table(rs)
            out = {}
            for stack in (False, True):
                m = RankerModel("x", scores, stack_on_baseline=stack).fit(rs[:t], tb[:t])
                out[stack] = m.predict(rs[t], tb[t])
            return out

        base = predict(races, sc)
        altered = copy.deepcopy(races)
        sc2 = copy.deepcopy(sc)
        for r in altered[t:]:                         # rewrite the target race and everything after it
            n = len(r.entries)
            r.entries = [Entry(e.driver, e.driver_id, e.team, e.grid, n - e.finish_position + 1, True) for e in r.entries]
        for r in altered[t + 1:]:                     # future scores change too
            sc2[r.key] = {d: -v for d, v in sc2[r.key].items()}
        changed = predict(altered, sc2)
        for stack in (False, True):
            for d, p in base[stack].items():
                self.assertAlmostEqual(p, changed[stack][d], places=12, msg=f"stack={stack} leaked for {d}")

    def test_load_scores_maps_codes_and_warns_on_unknown_drivers(self):
        import csv
        import tempfile
        races = make_races(n_races=3)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scores.csv"
            with open(path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["season", "round", "driver", "rank_score"])
                for e in races[0].entries:
                    w.writerow([races[0].season, races[0].round, e.driver, 1.0])
                w.writerow([races[0].season, races[0].round, "ZZZ", 0.5])
            scores, warns = load_scores(path, races)
        self.assertEqual(len(scores[races[0].key]), len(races[0].entries))
        self.assertEqual(len(warns), 1)


if __name__ == "__main__":
    unittest.main()
