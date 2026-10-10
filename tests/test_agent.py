import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge"))
from agent import SnapshotError, analyze_snapshot, validate_snapshot


class AgentTests(unittest.TestCase):
    def test_low_stock_recommendation(self):
        recs = analyze_snapshot({"country": "GER", "at_war": True, "stockpile_days": {"artillery_equipment": 2}})
        self.assertTrue(any(r.title == "Низкий запас: Артиллерия" and r.priority == "high" for r in recs))

    def test_no_signal_is_reported(self):
        recs = analyze_snapshot({"country": "USA", "at_war": False})
        self.assertEqual(recs[-1].title, "Срочных сигналов нет")

    def test_invalid_tag_rejected(self):
        with self.assertRaises(SnapshotError):
            validate_snapshot({"country": "Germany"})

    def test_bad_stock_rejected(self):
        with self.assertRaises(SnapshotError):
            validate_snapshot({"country": "GER", "stockpile_days": {"trucks": -1}})

    def test_air_and_manpower_signals(self):
        recs = analyze_snapshot({"country": "ITA", "at_war": True, "manpower": 50000, "air_superiority": 0.1})
        titles = {r.title for r in recs}
        self.assertIn("Мало людских ресурсов", titles)
        self.assertIn("Слабость в воздухе", titles)


if __name__ == "__main__":
    unittest.main()
