import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from oracle.circuits import circuit_lookup, outline

REAL = Path(__file__).resolve().parent.parent / "data" / "results"


def ellipse(n=300, a=1000.0, b=500.0):
    xs = [a * math.cos(2 * math.pi * t / n) for t in range(n + 1)]
    ys = [b * math.sin(2 * math.pi * t / n) for t in range(n + 1)]
    return xs, ys


class OutlineTests(unittest.TestCase):
    def test_scales_to_width_and_keeps_aspect(self):
        o = outline(*ellipse(), points=100)
        self.assertEqual(o["w"], 1000)
        self.assertAlmostEqual(o["h"] / o["w"], 0.5, delta=0.02)
        self.assertTrue(o["d"].startswith("M") and o["d"].endswith("Z"))

    def test_point_count(self):
        o = outline(*ellipse(), points=80)
        self.assertEqual(o["d"].count("L"), 79)

    def test_rotation_by_ninety_degrees_swaps_shape(self):
        o = outline(*ellipse(), rotation=90, points=100)
        self.assertGreater(o["h"], o["w"] * 0.9)          # a wide ellipse stood on its end

    def test_is_not_mirrored(self):
        # an asymmetric shape: the first sample must stay at the start/finish side after the flip
        xs = [0, 100, 200, 300, 300, 300, 200, 100, 0, 0] * 3
        ys = [0, 0, 0, 0, 100, 200, 200, 200, 200, 100] * 3
        o = outline(xs, ys, points=40)
        self.assertEqual(len(o["start"]), 2)

    def test_rejects_too_little_data(self):
        with self.assertRaises(ValueError):
            outline([0, 1, 2], [0, 1, 2])


class LookupTests(unittest.TestCase):
    def test_every_race_has_a_circuit(self):
        look = circuit_lookup(REAL)
        self.assertIn((2025, 1), look)
        self.assertEqual(look[(2026, 17)], "marina_bay")


if __name__ == "__main__":
    unittest.main()
