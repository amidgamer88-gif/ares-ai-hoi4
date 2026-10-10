import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from save_parser import SaveReadError, parse_save


class SaveParserTests(unittest.TestCase):
    def test_reads_text_save_country_scalars(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "minimal_text_save.hoi4"
        state = parse_save(fixture)
        self.assertEqual(state["country"], "GER")
        self.assertEqual(state["date"], "1939.9.1.12")
        self.assertEqual(state["game_version"], "1.19.3")
        self.assertEqual(state["stability"], 0.62)
        self.assertEqual(state["manpower"], 850000)
        self.assertTrue(state["at_war"])
        self.assertTrue(state["ares_marker_present"])

    def test_marker_must_be_in_direct_country_flags_block(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "minimal_text_save.hoi4"
        text = fixture.read_text(encoding="utf-8").replace(
            "\t\tflags={\n\t\t\tares_ai_companion_v1=1939.9.1.12\n\t\t}\n", ""
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old_save.hoi4"
            path.write_text(text.replace("custom={", "custom={\n\t\t\tares_ai_companion_v1=yes\n"), encoding="utf-8")
            self.assertFalse(parse_save(path)["ares_marker_present"])

    def test_ignores_nested_duplicate_fields(self):
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "minimal_text_save.hoi4"
        self.assertEqual(parse_save(fixture)["stability"], 0.62)

    def test_binary_save_gets_readable_setup_error(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "binary.hoi4"
            path.write_bytes(b"HOI4bin5\x00\x01")
            with self.assertRaisesRegex(SaveReadError, "бинарное сохранение"):
                parse_save(path)


if __name__ == "__main__":
    unittest.main()
