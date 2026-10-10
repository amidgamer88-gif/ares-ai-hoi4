import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop_app"))
from save_parser import ARES_COUNTRY_FLAG


class ModIntegrationTests(unittest.TestCase):
    def test_mod_marker_name_matches_companion_parser(self):
        script = ROOT / "mod" / "ares_ai" / "common" / "on_actions" / "ares_ai_on_actions.txt"
        contents = script.read_text(encoding="utf-8")
        self.assertIn("on_startup =", contents)
        self.assertIn("on_weekly =", contents)
        self.assertIn(f"set_country_flag = {ARES_COUNTRY_FLAG}", contents)
        self.assertIn(f"has_country_flag = {ARES_COUNTRY_FLAG}", contents)


if __name__ == "__main__":
    unittest.main()
