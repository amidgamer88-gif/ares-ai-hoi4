"""Local development receiver for opt-in ARES reports; binds to loopback only."""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8766
DATA_DIR = Path(os.environ.get("ARES_DATA_DIR", str(Path(__file__).resolve().parent / "data")))
DB_PATH = DATA_DIR / "ares_reports.sqlite3"
MAX_BODY = 32_000
MODES = {"ARES", "Vanilla control", "Other/unknown"}
STATE_KEYS = {"stability", "war_support", "manpower", "political_power", "at_war", "surrender_progress"}


def validate_report(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Ожидался JSON-объект отчёта.")
    if value.get("schema_version") != 1 or value.get("game") != "Hearts of Iron IV":
        raise ValueError("Неизвестная версия формата или игры.")
    mode = value.get("ares_mode")
    country = value.get("country")
    date = value.get("date")
    if mode not in MODES:
        raise ValueError("Неизвестный режим партии.")
    if not isinstance(country, str) or len(country) != 3 or not country.isalnum() or not country.isupper():
        raise ValueError("Тег страны должен содержать три заглавных символа.")
    if not isinstance(date, (str, int, float)):
        raise ValueError("В отчёте отсутствует игровая дата.")
    state = value.get("state")
    if not isinstance(state, dict):
        raise ValueError("Поле state должно быть объектом.")
    clean_state = {}
    for key in STATE_KEYS:
        item = state.get(key)
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError(f"Недопустимое значение поля {key}.")
        clean_state[key] = item
    clean = {
        "schema_version": 1,
        "game": "Hearts of Iron IV",
        "game_version": value.get("game_version") if isinstance(value.get("game_version"), str) else None,
        "save_version": value.get("save_version") if isinstance(value.get("save_version"), (str, int, float)) else None,
        "ares_mode": mode,
        "ares_marker_present": value.get("ares_marker_present") if isinstance(value.get("ares_marker_present"), bool) else None,
        "country": country,
        "date": str(date),
        "state": clean_state,
        "parsed_fields": [x for x in value.get("parsed_fields", []) if isinstance(x, str)][:32] if isinstance(value.get("parsed_fields", []), list) else [],
    }
    return clean


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS reports (receipt_id TEXT PRIMARY KEY, received_at_utc TEXT NOT NULL, payload_json TEXT NOT NULL)")
        connection.commit()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, {"status": "ready", "schema_version": 1})
        else:
            self._send(404, {"error": "Маршрут не найден."})

    def do_POST(self) -> None:
        if self.path != "/api/v1/reports":
            self._send(404, {"error": "Маршрут не найден."})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_BODY:
                raise ValueError("Размер отчёта должен быть от 1 байта до 32 КБ.")
            raw = json.loads(self.rfile.read(size).decode("utf-8"))
            report = validate_report(raw)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        receipt = uuid.uuid4().hex
        received = datetime.now(timezone.utc).isoformat()
        with closing(sqlite3.connect(DB_PATH)) as connection:
            connection.execute("INSERT INTO reports(receipt_id, received_at_utc, payload_json) VALUES (?, ?, ?)", (receipt, received, json.dumps(report, ensure_ascii=False)))
            connection.commit()
        self._send(201, {"receipt_id": receipt, "received_at_utc": received})

    def log_message(self, fmt: str, *args) -> None:
        # Deliberately omit remote address and request body from logs.
        print("[ARES community] " + fmt % args)


def serve(host: str = HOST, port: int = PORT) -> None:
    initialize_database()
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"ARES local community receiver: http://{host}:{port}")
    print("Loopback only; this development server is not configured for public hosting.")
    print("Stop with Ctrl+C. Reports are stored in:", DB_PATH)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nReceiver stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
