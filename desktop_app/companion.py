"""ARES Companion: local Windows desktop monitor for HOI4 autosaves."""
from __future__ import annotations

import json
import os
import queue
import re
import shutil
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from save_parser import SaveReadError, parse_save

APP_NAME = "ARES AI Companion"


def documents_dir() -> Path:
    candidates = [Path.home() / "Documents", Path.home() / "OneDrive" / "Documents"]
    return next((p for p in candidates if p.exists()), candidates[0])


def hoi_dir() -> Path:
    return documents_dir() / "Paradox Interactive" / "Hearts of Iron IV"


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    location = base / "ARES AI Companion"
    location.mkdir(parents=True, exist_ok=True)
    return location


CONFIG_PATH = app_data_dir() / "config.json"
HISTORY_PATH = app_data_dir() / "local_reports.jsonl"


def load_config() -> dict:
    default = {
        "config_version": 2,
        "save_path": str(hoi_dir() / "save games" / "autosave.hoi4"),
        "poll_seconds": 10,
        "mode": "Auto-detect",
        "auto_start": True,
        "community_upload_enabled": False,
        "community_server_url": "",
    }
    try:
        saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(saved, dict):
            prior_version = saved.get("config_version", 1)
            default.update(saved)
            if not isinstance(prior_version, int) or prior_version < 2:
                # Older releases defaulted to a manual unknown label, which would bypass marker detection.
                default["mode"] = "Auto-detect"
                default["config_version"] = 2
    except (OSError, json.JSONDecodeError):
        pass
    return default


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def enable_text_save_format(path: Path) -> Path | None:
    """Switch future saves to text, preserving a byte-for-byte settings backup."""
    original = path.read_bytes()
    decoded = original.decode("utf-8-sig")
    updated, count = re.subn(r"(?m)^(\s*save_as_binary\s*=\s*)yes\b", r"\1no", decoded, count=1)
    if count == 0:
        if re.search(r"(?m)^\s*save_as_binary\s*=\s*no\b", decoded):
            return None
        raise OSError("В settings.txt не найдена настройка save_as_binary.")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup = path.with_name(f"settings.txt.ares-backup-{stamp}")
    shutil.copy2(path, backup)
    prefix = "\ufeff" if original.startswith(b"\xef\xbb\xbf") else ""
    temp = path.with_name(path.name + ".ares-tmp")
    with temp.open("w", encoding="utf-8", newline="") as stream:
        stream.write(prefix + updated)
    os.replace(temp, path)
    return backup


def analyze_state(state: dict) -> list[dict[str, str]]:
    signals = []
    if isinstance(state.get("manpower"), (int, float)) and state["manpower"] < 100_000:
        signals.append({"priority": "high", "title": "Мало manpower", "detail": f"В сейве указано {state['manpower']:,}. Проверьте призыв и потери."})
    if isinstance(state.get("stability"), (int, float)) and state["stability"] < 0.35:
        signals.append({"priority": "medium", "title": "Низкая стабильность", "detail": f"Показатель: {state['stability']:.0%}. Проверьте национальные духи и доступные решения."})
    if isinstance(state.get("war_support"), (int, float)) and state["war_support"] < 0.3:
        signals.append({"priority": "medium", "title": "Низкая поддержка войны", "detail": f"Показатель: {state['war_support']:.0%}."})
    if state.get("at_war") is True:
        signals.append({"priority": "info", "title": "Страна воюет", "detail": "Сравните со следующим снимком изменения manpower, стабильности и поддержки войны."})
    if not signals:
        signals.append({"priority": "info", "title": "Снимок принят", "detail": "Разобраны базовые поля страны. Недостающие поля отмечены как «не извлечено»; приложение пока не управляет игрой."})
    return signals


def make_report(state: dict, mode: str) -> dict:
    marker_present = state.get("ares_marker_present") is True
    if mode == "Auto-detect":
        resolved_mode = "ARES" if marker_present else "Other/unknown"
    elif mode in ("Vanilla control", "Other/unknown"):
        resolved_mode = mode
    else:
        resolved_mode = "Other/unknown"
    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "game": "Hearts of Iron IV",
        "game_version": state.get("game_version"),
        "save_version": state.get("save_version"),
        "ares_mode": resolved_mode,
        "ares_marker_present": marker_present,
        "country": state.get("country"),
        "date": state.get("date"),
        "state": {key: state.get(key) for key in ("stability", "war_support", "manpower", "political_power", "at_war", "surrender_progress")},
        "parsed_fields": state.get("parsed_fields", []),
    }


def validate_endpoint(endpoint: str):
    try:
        parsed = urllib.parse.urlsplit(endpoint.strip())
        hostname = parsed.hostname
        parsed.port  # Validate the port syntax now, before the watcher thread uses it.
    except ValueError as exc:
        raise ValueError("Укажите корректный адрес сервера.") from exc
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and hostname in local_hosts):
        raise ValueError("Для внешнего сервера нужен HTTPS. HTTP разрешён только для localhost.")
    if not hostname or parsed.username or parsed.password:
        raise ValueError("Укажите корректный адрес сервера без логина и пароля в URL.")
    return parsed


def upload_report(report: dict, endpoint: str) -> str:
    validate_endpoint(endpoint)
    clean = {key: report.get(key) for key in ("schema_version", "game", "game_version", "save_version", "ares_mode", "ares_marker_present", "country", "date", "state", "parsed_fields")}
    request = urllib.request.Request(endpoint.strip(), data=json.dumps(clean, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read(4_000).decode("utf-8"))
            if response.status not in (200, 201) or not payload.get("receipt_id"):
                raise ValueError("Сервер не подтвердил получение отчёта.")
            return str(payload["receipt_id"])
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"Не удалось отправить отчёт: {exc}") from exc


class SaveWatcher(threading.Thread):
    def __init__(self, path: str, interval_seconds: int, mode: str, community: dict, events):
        super().__init__(daemon=True)
        self.settings_lock = threading.Lock()
        self.settings = {
            "path": path,
            "interval_seconds": interval_seconds,
            "mode": mode,
            "community": dict(community),
        }
        self.events = events
        self.stop_event = threading.Event()

    def update_settings(self, path: str, interval_seconds: int, mode: str, community: dict):
        with self.settings_lock:
            self.settings = {
                "path": path,
                "interval_seconds": interval_seconds,
                "mode": mode,
                "community": dict(community),
            }

    def settings_snapshot(self) -> dict:
        with self.settings_lock:
            return {**self.settings, "community": dict(self.settings["community"])}

    def stop(self):
        self.stop_event.set()

    def run(self):
        self.events.put(("status", "Наблюдение включено. Жду готовый файл автосохранения…"))
        last_done = None
        candidate = None
        stable = 0
        last_error = None
        while True:
            settings = self.settings_snapshot()
            if self.stop_event.wait(settings["interval_seconds"]):
                break
            settings = self.settings_snapshot()
            path = Path(settings["path"])
            try:
                stat = path.stat()
            except OSError:
                if last_error != "missing":
                    self.events.put(("status", f"Пока не найден файл: {path}"))
                    last_error = "missing"
                continue
            signature = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
            if signature == last_done:
                continue
            if signature == candidate:
                stable += 1
            else:
                candidate, stable = signature, 0
                continue
            # Wait through two unchanged polls so we don't read while HOI4 writes the save.
            if stable < 2:
                continue
            try:
                state = parse_save(path)
                report = make_report(state, settings["mode"])
                report["recommendations"] = analyze_state(state)
                with HISTORY_PATH.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(report, ensure_ascii=False) + "\n")
                self.events.put(("snapshot", report))
                self.events.put(("status", f"Обновлено по автосохранению от {datetime.fromtimestamp(stat.st_mtime).strftime('%d.%m.%Y %H:%M:%S')}"))
                community = settings["community"]
                if community.get("enabled") and community.get("url"):
                    try:
                        receipt = upload_report(report, community["url"])
                    except ValueError as exc:
                        self.events.put(("upload_error", str(exc)))
                    else:
                        self.events.put(("upload", receipt))
                last_done = signature
                last_error = None
            except (SaveReadError, OSError) as exc:
                message = str(exc)
                if message != last_error:
                    self.events.put(("error", message))
                    last_error = message


class AresApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("880x650")
        self.minsize(760, 560)
        self.config_data = load_config()
        self.events: queue.Queue = queue.Queue()
        self.watcher: SaveWatcher | None = None
        self.status_var = tk.StringVar(value="Готово к запуску наблюдения.")
        self.path_var = tk.StringVar(value=self.config_data["save_path"])
        self.interval_var = tk.StringVar(value=str(self.config_data["poll_seconds"]))
        saved_mode = self.config_data.get("mode")
        if saved_mode not in ("Auto-detect", "Vanilla control", "Other/unknown"):
            saved_mode = "Auto-detect"
            self.config_data["mode"] = saved_mode
        self.mode_var = tk.StringVar(value=saved_mode)
        self.community_url_var = tk.StringVar(value=self.config_data.get("community_server_url", ""))
        self.community_enabled_var = tk.BooleanVar(value=bool(self.config_data.get("community_upload_enabled", False)))
        self.last_report: dict | None = None
        self._style()
        self._build()
        if self.config_data.get("auto_start", True):
            self.after(250, self.start_watcher)
        self.after(200, self._drain_events)
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _style(self):
        self.configure(bg="#10151d")
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#10151d")
        style.configure("Card.TFrame", background="#1a2430")
        style.configure("TLabel", background="#10151d", foreground="#edf2f6", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"))
        style.configure("Sub.TLabel", foreground="#aab9c7")
        style.configure("Card.TLabel", background="#1a2430")
        style.configure("TButton", font=("Segoe UI", 10), padding=8)
        style.configure("Accent.TButton", background="#69d1b0", foreground="#10151d", font=("Segoe UI", 10, "bold"))
        style.configure("TNotebook", background="#10151d", borderwidth=0)
        style.configure("TNotebook.Tab", background="#1a2430", foreground="#edf2f6", padding=(14, 8))

    def _build(self):
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="ARES AI Companion", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Локальное наблюдение за партией HOI4", style="Sub.TLabel").pack(anchor="w", pady=(2, 0))
        self.tabs = ttk.Notebook(outer)
        self.tabs.pack(fill="both", expand=True)
        self.observe_tab = ttk.Frame(self.tabs, padding=16)
        self.settings_tab = ttk.Frame(self.tabs, padding=16)
        self.community_tab = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.observe_tab, text="Партия")
        self.tabs.add(self.settings_tab, text="Настройки")
        self.tabs.add(self.community_tab, text="Сообщество")
        self._build_observe()
        self._build_settings()
        self._build_community()
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(12, 0))
        ttk.Label(footer, textvariable=self.status_var, style="Sub.TLabel").pack(side="left", fill="x", expand=True)

    def _build_observe(self):
        tab = self.observe_tab
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=(0, 12))
        self.start_button = ttk.Button(row, text="Остановить наблюдение", command=self.toggle_watcher, style="Accent.TButton")
        self.start_button.pack(side="left")
        ttk.Button(row, text="Открыть папку отчётов", command=self.open_data_folder).pack(side="left", padx=8)
        self.state_label = ttk.Label(tab, text="Пока нет снимка партии.", style="Sub.TLabel")
        self.state_label.pack(anchor="w", pady=(0, 8))
        self.summary = tk.Text(tab, height=8, wrap="word", bg="#1a2430", fg="#edf2f6", insertbackground="#edf2f6", relief="flat", padx=14, pady=12, font=("Segoe UI", 11))
        self.summary.pack(fill="x", pady=(0, 12))
        self.summary.configure(state="disabled")
        ttk.Label(tab, text="Диагностика и рекомендации", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(2, 5))
        self.results = tk.Text(tab, height=11, wrap="word", bg="#1a2430", fg="#edf2f6", insertbackground="#edf2f6", relief="flat", padx=14, pady=12, font=("Segoe UI", 10))
        self.results.pack(fill="both", expand=True)
        self.results.configure(state="disabled")

    def _build_settings(self):
        tab = self.settings_tab
        ttk.Label(tab, text="Файл автосохранения", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(tab, text="ARES читает сейв в режиме только чтения и ждёт, пока HOI4 закончит его записывать.", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(3, 8))
        line = ttk.Frame(tab)
        line.pack(fill="x", pady=(0, 15))
        ttk.Entry(line, textvariable=self.path_var).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Выбрать…", command=self.choose_save).pack(side="left", padx=(8, 0))
        ttk.Label(tab, text="Частота проверки", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        line = ttk.Frame(tab)
        line.pack(fill="x", pady=(3, 15))
        ttk.Spinbox(line, from_=3, to=120, increment=1, textvariable=self.interval_var, width=8).pack(side="left")
        ttk.Label(line, text="секунд", style="Sub.TLabel").pack(side="left", padx=8)
        ttk.Label(tab, text="Определение режима партии", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Combobox(tab, textvariable=self.mode_var, values=("Auto-detect", "Vanilla control", "Other/unknown"), state="readonly", width=24).pack(anchor="w", pady=(3, 4))
        ttk.Label(tab, text="Автоопределение ищет маркер, который ARES записывает в сейв. Маркер сохраняется в кампании и сам по себе не доказывает, что мод включён прямо сейчас. Для контрольной партии выберите Vanilla control вручную.", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(0, 15))
        ttk.Button(tab, text="Сохранить настройки", command=self.save_settings, style="Accent.TButton").pack(anchor="w", pady=(0, 18))
        ttk.Separator(tab).pack(fill="x", pady=8)
        ttk.Label(tab, text="Формат сохранения HOI4", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(8, 3))
        ttk.Label(tab, text="Текущие бинарные сейвы не читаются этим прототипом. Чтобы анализировать следующие автосохранения, включите текстовый формат. Приложение не меняет эту настройку само.", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(0, 8))
        buttons = ttk.Frame(tab)
        buttons.pack(anchor="w")
        ttk.Button(buttons, text="Включить текстовые сохранения", command=self.enable_text_saves).pack(side="left")
        ttk.Button(buttons, text="Открыть настройки HOI4", command=self.open_hoi_settings).pack(side="left", padx=8)
        ttk.Label(tab, text="После смены настройки перезапустите игру и дождитесь нового автосохранения. Старые сейвы не меняются.", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(8, 0))

    def _build_community(self):
        tab = self.community_tab
        ttk.Label(tab, text="Общий сбор отчётов · эксперимент", font=("Segoe UI", 16, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(tab, text="Отправка выключена по умолчанию. Для локальной проверки сначала запустите приёмник из комплекта, затем укажите его адрес и отдельно подтвердите согласие.", wraplength=760).pack(anchor="w", pady=(0, 12))
        ttk.Label(tab, text="Адрес сервера приёма отчётов", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        line = ttk.Frame(tab)
        line.pack(fill="x", pady=(3, 10))
        ttk.Entry(line, textvariable=self.community_url_var).pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Сохранить адрес", command=self.save_community_settings).pack(side="left", padx=(8, 0))
        ttk.Label(tab, text="Адрес для приёмника на этом компьютере: http://127.0.0.1:8766/api/v1/reports", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(0, 8))
        ttk.Checkbutton(tab, text="Разрешить отправку отчётов с игровыми данными после новых автосохранений", variable=self.community_enabled_var, command=self.toggle_community_upload).pack(anchor="w", pady=(0, 12))
        card = ttk.Frame(tab, style="Card.TFrame", padding=14)
        card.pack(fill="x", pady=(0, 12))
        ttk.Label(card, text="Отчёт содержит версию игры, тег страны, дату, наличие ARES-маркера и показатели страны. Путь к файлу, имя пользователя, Steam ID и сам сейв не включаются. Это не гарантия полной анонимности: игровые данные могут быть узнаваемы в сочетании с другими сведениями.", style="Card.TLabel", wraplength=740).pack(anchor="w")
        ttk.Label(tab, text="Экспорт отчёта для ручного просмотра", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(10, 3))
        ttk.Label(tab, text="Без адреса и согласия данные останутся локально. Экспорт отчёта не загружает его. Приёмник из комплекта работает только на этом компьютере и пока ничего не обучает.", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(0, 8))
        ttk.Button(tab, text="Экспортировать последний отчёт…", command=self.export_report).pack(anchor="w")
        ttk.Label(tab, text="Для общего обучения потребуется отдельное добровольное согласие, описание срока хранения и возможность удалить отправленные данные.", style="Sub.TLabel", wraplength=760).pack(anchor="w", pady=(18, 0))

    def choose_save(self):
        name = filedialog.askopenfilename(title="Выберите файл автосохранения HOI4", filetypes=(("Сохранения HOI4", "*.hoi4"), ("Все файлы", "*.*")))
        if name:
            self.path_var.set(name)
            self.save_settings()

    def save_settings(self):
        try:
            interval = max(3, min(120, int(self.interval_var.get())))
        except ValueError:
            messagebox.showerror(APP_NAME, "Интервал должен быть целым числом от 3 до 120 секунд.")
            return
        self.config_data.update({"save_path": self.path_var.get(), "poll_seconds": interval, "mode": self.mode_var.get()})
        save_config(self.config_data)
        self.status_var.set("Настройки сохранены.")
        self._refresh_watcher_settings()

    def _current_watcher_settings(self):
        try:
            interval = max(3, min(120, int(self.interval_var.get())))
        except (TypeError, ValueError):
            interval = 10
            self.interval_var.set("10")
        mode = self.mode_var.get()
        if mode not in ("Auto-detect", "Vanilla control", "Other/unknown"):
            mode = "Auto-detect"
            self.mode_var.set(mode)
        community = {
            "enabled": bool(self.community_enabled_var.get()),
            "url": self.community_url_var.get().strip(),
        }
        return self.path_var.get().strip(), interval, mode, community

    def _refresh_watcher_settings(self):
        if self.watcher and self.watcher.is_alive():
            self.watcher.update_settings(*self._current_watcher_settings())

    def start_watcher(self):
        if self.watcher and self.watcher.is_alive():
            return
        self.watcher = SaveWatcher(*self._current_watcher_settings(), self.events)
        self.watcher.start()
        self.start_button.configure(text="Остановить наблюдение")

    def stop_watcher(self):
        if self.watcher:
            self.watcher.stop()
            self.watcher = None
        self.start_button.configure(text="Начать наблюдение")
        self.status_var.set("Наблюдение остановлено.")

    def toggle_watcher(self):
        if self.watcher and self.watcher.is_alive():
            self.stop_watcher()
        else:
            self.start_watcher()

    def _drain_events(self):
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "status":
                self.status_var.set(payload)
            elif kind == "error":
                self.status_var.set("Нужна настройка сохранений.")
                self._set_text(self.results, "Не удалось прочитать последнее сохранение.\n\n" + payload)
            elif kind == "upload":
                self.status_var.set(f"Отчёт отправлен с вашего согласия. Номер приёма: {payload}")
            elif kind == "upload_error":
                self.status_var.set("Локальный отчёт сохранён; отправка не удалась: " + payload)
            elif kind == "snapshot":
                self.last_report = payload
                state = payload["state"]
                marker = payload.get("ares_marker_present")
                marker_text = "найден (ARES был загружен в этой кампании)" if marker is True else "не найден (ваниль или сейв до установки интеграции)"
                summary = [f"Страна: {payload.get('country') or 'не определена'}", f"Игровая дата: {payload.get('date') or 'не определена'}", f"Версия игры: {payload.get('game_version') or 'не извлечена'}", f"Режим отчёта: {payload.get('ares_mode')}", f"Маркер мода в сейве: {marker_text}"]
                for label, key in (("Стабильность", "stability"), ("Поддержка войны", "war_support"), ("Manpower", "manpower"), ("Political power", "political_power"), ("Война", "at_war")):
                    value = state.get(key)
                    if isinstance(value, float) and 0 <= value <= 1:
                        value = f"{value:.0%}"
                    elif value is None:
                        value = "не извлечено"
                    summary.append(f"{label}: {value}")
                marker_status = "ARES-маркер найден" if marker is True else "ARES-маркер не найден"
                self.state_label.configure(text=f"Последний снимок · {marker_status} · {len(payload.get('parsed_fields', []))} показателей распознано")
                self._set_text(self.summary, "\n".join(summary))
                self._set_text(self.results, "\n\n".join(f"[{x['priority'].upper()}] {x['title']}\n{x['detail']}" for x in payload["recommendations"]))
        self.after(200, self._drain_events)

    @staticmethod
    def _set_text(widget, value):
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def open_data_folder(self):
        os.startfile(str(app_data_dir()))

    def open_hoi_settings(self):
        path = hoi_dir() / "settings.txt"
        if not path.exists():
            messagebox.showerror(APP_NAME, f"Не найден файл настроек HOI4:\n{path}")
            return
        os.startfile(str(path))

    def enable_text_saves(self):
        path = hoi_dir() / "settings.txt"
        try:
            backup = enable_text_save_format(path)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror(APP_NAME, f"Не удалось изменить настройки HOI4: {exc}")
            return
        if backup is None:
            messagebox.showinfo(APP_NAME, "Текстовый формат уже включён. Перезапустите HOI4, если игра была открыта.")
            return
        messagebox.showinfo(APP_NAME, "Готово. Исходный settings.txt сохранён рядом в резервной копии.\n\nПерезапустите HOI4 и дождитесь следующего автосохранения. Старые сейвы не меняются.")
        self.status_var.set(f"Текстовые сейвы включены; резервная копия: {backup.name}")

    def export_report(self):
        if not self.last_report:
            messagebox.showinfo(APP_NAME, "Сначала дождитесь, пока приложение разберёт автосохранение.")
            return
        path = filedialog.asksaveasfilename(title="Сохранить отчёт ARES", defaultextension=".json", initialfile="ares-report.json", filetypes=(("JSON", "*.json"),))
        if path:
            Path(path).write_text(json.dumps(self.last_report, ensure_ascii=False, indent=2), encoding="utf-8")
            self.status_var.set("Отчёт сохранён локально; он никуда не отправлялся.")

    def save_community_settings(self):
        url = self.community_url_var.get().strip()
        if url:
            try:
                validate_endpoint(url)
            except ValueError as exc:
                messagebox.showerror(APP_NAME, str(exc))
                return
        self.config_data["community_server_url"] = url
        self.config_data["community_upload_enabled"] = self.community_enabled_var.get()
        save_config(self.config_data)
        self.status_var.set("Настройки сообщества сохранены.")
        self._refresh_watcher_settings()

    def toggle_community_upload(self):
        if self.community_enabled_var.get():
            if not self.community_url_var.get().strip():
                self.community_enabled_var.set(False)
                messagebox.showwarning(APP_NAME, "Сначала укажите адрес сервера. Пока у проекта нет публичного сервера.")
                return
            accepted = messagebox.askyesno(
                "Согласие на отправку отчётов",
                "После новых автосохранений будут отправляться: версия схемы и игры (если доступна), версия сохранения, режим отчёта, наличие ARES-маркера в сейве, тег страны, игровая дата и извлечённые показатели страны.\n\n" +
                "Не отправляются: сам сейв, путь к файлу, имя пользователя, Steam ID и рекомендации. Игровые данные всё же могут быть узнаваемы при сопоставлении с другими сведениями. Отправка продолжится до выключения этой галочки. Согласны?",
            )
            if not accepted:
                self.community_enabled_var.set(False)
        self.save_community_settings()

    def close(self):
        if self.watcher:
            self.watcher.stop()
        self.destroy()


if __name__ == "__main__":
    AresApp().mainloop()
