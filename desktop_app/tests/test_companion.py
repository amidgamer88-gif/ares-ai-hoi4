import json
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop_app"))
sys.path.insert(0, str(ROOT / "community"))

import companion
import server


class CompanionTests(unittest.TestCase):
    def test_report_uses_save_marker_and_allows_control_override(self):
        state = {"country": "GER", "date": "1939.1.1", "ares_marker_present": True}
        self.assertEqual(companion.make_report(state, "Auto-detect")["ares_mode"], "ARES")
        self.assertEqual(companion.make_report(state, "Vanilla control")["ares_mode"], "Vanilla control")
        state["ares_marker_present"] = False
        self.assertEqual(companion.make_report(state, "Auto-detect")["ares_mode"], "Other/unknown")

    def test_text_format_switch_keeps_byte_exact_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder) / "settings.txt"
            original = b"language=\"l_english\"\r\nsave_as_binary=yes\r\nother=yes\r\n"
            settings.write_bytes(original)

            backup = companion.enable_text_save_format(settings)

            self.assertIsNotNone(backup)
            self.assertEqual(backup.read_bytes(), original)
            self.assertEqual(settings.read_bytes(), original.replace(b"save_as_binary=yes", b"save_as_binary=no"))
            self.assertIsNone(companion.enable_text_save_format(settings))

    def test_upload_uses_local_receiver_and_drops_private_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            old_dir, old_db = server.DATA_DIR, server.DB_PATH
            server.DATA_DIR = Path(folder)
            server.DB_PATH = server.DATA_DIR / "test.sqlite3"
            server.initialize_database()
            http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                endpoint = f"http://127.0.0.1:{http.server_address[1]}/api/v1/reports"
                report = {
                    "schema_version": 1,
                    "game": "Hearts of Iron IV",
                    "game_version": "1.19.3",
                    "save_version": 30,
                    "ares_mode": "ARES",
                    "ares_marker_present": True,
                    "country": "GER",
                    "date": "1939.1.1",
                    "state": {"manpower": 50000},
                    "parsed_fields": ["manpower"],
                    "save_path": "C:/Users/private/save.hoi4",
                    "recommendations": [{"title": "private local detail"}],
                }

                receipt = companion.upload_report(report, endpoint)

                with closing(sqlite3.connect(server.DB_PATH)) as connection:
                    payload = json.loads(connection.execute("SELECT payload_json FROM reports WHERE receipt_id=?", (receipt,)).fetchone()[0])
                self.assertEqual(payload["country"], "GER")
                self.assertTrue(payload["ares_marker_present"])
                self.assertNotIn("save_path", payload)
                self.assertNotIn("recommendations", payload)
            finally:
                http.shutdown()
                http.server_close()
                thread.join(timeout=2)
                server.DATA_DIR, server.DB_PATH = old_dir, old_db

    def test_external_http_endpoint_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            companion.validate_endpoint("http://example.org/api/v1/reports")


if __name__ == "__main__":
    unittest.main()
