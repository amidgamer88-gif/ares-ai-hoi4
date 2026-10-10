import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class ServerTests(unittest.TestCase):
    def test_validate_report_removes_unexpected_fields(self):
        report = {"schema_version": 1, "game": "Hearts of Iron IV", "ares_mode": "ARES", "ares_marker_present": True, "country": "GER", "date": "1939.1.1", "state": {"stability": 0.5}, "save_path": "private"}
        clean = server.validate_report(report)
        self.assertNotIn("save_path", clean)
        self.assertTrue(clean["ares_marker_present"])

    def test_rejects_unknown_mode(self):
        with self.assertRaises(ValueError):
            server.validate_report({"schema_version": 1, "game": "Hearts of Iron IV", "ares_mode": "unknown-mode", "country": "GER", "date": "1939.1.1", "state": {}})

    def test_local_post_returns_receipt(self):
        with tempfile.TemporaryDirectory() as folder:
            old_dir, old_db = server.DATA_DIR, server.DB_PATH
            server.DATA_DIR = Path(folder)
            server.DB_PATH = server.DATA_DIR / "test.sqlite3"
            server.initialize_database()
            http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                body = {"schema_version": 1, "game": "Hearts of Iron IV", "ares_mode": "ARES", "country": "GER", "date": "1939.1.1", "state": {"manpower": 50000}}
                req = Request(f"http://127.0.0.1:{http.server_address[1]}/api/v1/reports", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                with urlopen(req, timeout=3) as response:
                    result = json.load(response)
                    self.assertEqual(response.status, 201)
                    self.assertTrue(result["receipt_id"])
            finally:
                http.shutdown()
                http.server_close()
                server.DATA_DIR, server.DB_PATH = old_dir, old_db


if __name__ == "__main__":
    unittest.main()
