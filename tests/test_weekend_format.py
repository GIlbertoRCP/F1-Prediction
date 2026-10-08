import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from weekend_format import is_sprint_weekend


class FakeEvent:
    def __init__(self, names):
        self.names = names

    def get_session_name(self, i):
        if not 1 <= i <= len(self.names):
            raise ValueError("no such session")
        return self.names[i - 1]


# Session layouts copied from the FastF1 schedule cached in this project
STANDARD = ["Practice 1", "Practice 2", "Practice 3", "Qualifying", "Race"]
SPRINT_2022 = ["Practice 1", "Qualifying", "Practice 2", "Sprint", "Race"]
SPRINT_2023 = ["Practice 1", "Qualifying", "Sprint Shootout", "Sprint", "Race"]
SPRINT_2024_PLUS = ["Practice 1", "Sprint Qualifying", "Sprint", "Qualifying", "Race"]


class SprintDetectionTests(unittest.TestCase):
    def test_fixed_detection_covers_every_sprint_era(self):
        for layout in (SPRINT_2022, SPRINT_2023, SPRINT_2024_PLUS):
            self.assertTrue(is_sprint_weekend(FakeEvent(layout)), layout)

    def test_standard_weekend_is_not_sprint(self):
        self.assertFalse(is_sprint_weekend(FakeEvent(STANDARD)))

    def test_legacy_detection_missed_2024_plus_sprints(self):
        """Documents the original bug: 2024+ sprint weekends were reported as standard."""
        self.assertFalse(is_sprint_weekend(FakeEvent(SPRINT_2024_PLUS), legacy=True))
        self.assertTrue(is_sprint_weekend(FakeEvent(SPRINT_2023), legacy=True))

    def test_short_or_broken_events_do_not_raise(self):
        self.assertFalse(is_sprint_weekend(FakeEvent(["Practice 1", "Race"])))


if __name__ == "__main__":
    unittest.main()
