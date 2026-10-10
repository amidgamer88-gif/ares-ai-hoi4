"""Local ARES dashboard; binds only to 127.0.0.1 and uses Python stdlib."""
from __future__ import annotations

import json
import os
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from agent import SnapshotError, analyze_snapshot, validate_snapshot

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
HOST, PORT = "127.0.0.1", 8765


def diagnostics() -> dict:
    docs = Path.home() / "Documents" / "Paradox Interactive" / "Hearts of Iron IV"
    candidates = [docs, Path(os.environ.get("USERPROFILE", str(Path.home()))) / "OneDrive" / "Documents" / "Paradox Interactive" / "Hearts of Iron IV"]
    game_docs = next((p for p in candidates if p.exists()), candidates[0])
    mod = HERE.parent / "mod" / "ares_ai"
    return {
        "bridge": "готов",
        "listen": f"http://{HOST}:{PORT}",
        "python": __import__("sys").version.split()[0],
        "mod_source": str(mod),
        "mod_source_found": (mod / "common" / "ai_strategy" / "ares_ai.txt").exists(),
        "hoi_documents": str(game_docs),
        "hoi_documents_found": game_docs.exists(),
        "logs": {name: str(game_docs / "logs" / name) for name in ("error.log", "game.log")},
        "log_files_found": {name: (game_docs / "logs" / name).exists() for name in ("error.log", "game.log")},
        "mode": "Только локальный анализ вручную переданного снимка; автоматическое управление игрой не подключено.",
    }


PAGE = r'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>ARES AI Bridge</title>
<style>
:root{color-scheme:dark;--bg:#10151d;--panel:#1a2430;--line:#304254;--text:#edf2f6;--muted:#aab9c7;--accent:#69d1b0}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px/1.5 system-ui,Segoe UI,sans-serif}main{max-width:1050px;margin:auto;padding:30px 20px}h1{margin:0;font-size:2rem}h2{font-size:1.18rem;margin:0 0 12px}.sub,.muted{color:var(--muted)}.badge{display:inline-block;border:1px solid var(--accent);color:var(--accent);padding:3px 9px;border-radius:20px;font-size:.85rem;margin:12px 0 20px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px;margin:0 0 16px}textarea{width:100%;min-height:300px;background:#0b1016;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:12px;font:13px/1.45 Consolas,monospace}button{background:var(--accent);border:0;border-radius:8px;padding:10px 16px;font-weight:700;cursor:pointer;margin-top:10px}.rec{border-left:3px solid var(--accent);padding:10px 12px;background:#111922;margin:9px 0;border-radius:4px}.rec.high{border-color:#ff7777}.rec.medium{border-color:#ffca65}.rec.info{border-color:#68aaff}.rec b{display:block}.err{color:#ff9d9d;white-space:pre-wrap}.diag{display:grid;grid-template-columns:210px 1fr;gap:5px 12px;font-size:.9rem;overflow-wrap:anywhere}.yes{color:var(--accent)}.no{color:#ffca65}@media(max-width:750px){.grid{grid-template-columns:1fr}.diag{grid-template-columns:1fr}}
</style><main><h1>ARES AI Bridge</h1><div class="sub">Локальный аналитический прототип для Hearts of Iron IV</div><div class="badge">Работает на этом компьютере · внешние подключения отключены</div>
<div class="grid"><section class="card"><h2>Снимок страны</h2><div class="muted">Измените пример или вставьте JSON по своей кампании. Рекомендации — эвристические подсказки.</div><textarea id="snapshot" spellcheck="false"></textarea><button id="analyze">Анализировать</button><div id="error" class="err"></div></section><section class="card"><h2>Рекомендации</h2><div id="results" class="muted">Вставьте снимок и нажмите «Анализировать».</div></section></div>
<section class="card"><h2>Диагностика</h2><div class="diag" id="diag">Загрузка…</div></section><section class="card"><h2>Что подключено</h2><div class="muted">Мод меняет веса production AI strategy по состоянию войны. Bridge не управляет процессом HOI4 и не получает состояние игры автоматически. Чтобы проверить поведение мода, используйте в игре команду <code>aiview</code> и журналы игры.</div></section></main>
<script>
const $=id=>document.getElementById(id);async function json(url,opt){let r=await fetch(url,opt);let d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d}function escape(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
json('/api/sample').then(x=>$('snapshot').value=JSON.stringify(x,null,2));json('/api/diagnostics').then(d=>{$('diag').innerHTML=Object.entries(d).map(([k,v])=>`<b>${escape(k.replaceAll('_',' '))}</b><span class="${typeof v==='boolean'?(v?'yes':'no'):''}">${escape(typeof v==='object'?JSON.stringify(v):v)}</span>`).join('')});
$('analyze').onclick=async()=>{ $('error').textContent='';try{const d=await json('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:$('snapshot').value});$('results').innerHTML=d.recommendations.map(r=>`<div class="rec ${escape(r.priority)}"><b>${escape(r.title)}</b>${escape(r.detail)}</div>`).join('')}catch(e){$('error').textContent=e.message}};
</script></html>'''


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self) -> None:
        if self.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/diagnostics":
            self._json(200, diagnostics())
        elif self.path == "/api/sample":
            with (HERE / "sample_snapshot.json").open(encoding="utf-8") as f:
                self._json(200, json.load(f))
        else:
            self._json(404, {"error": "Страница не найдена."})

    def do_POST(self) -> None:
        if self.path != "/api/analyze":
            self._json(404, {"error": "Маршрут не найден."})
            return
        if int(self.headers.get("Content-Length", "0")) > 100_000:
            self._json(413, {"error": "Снимок слишком большой (лимит 100 КБ)."})
            return
        try:
            raw = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8"))
            snapshot = validate_snapshot(raw)
            recommendations = [r.as_dict() for r in analyze_snapshot(snapshot)]
            DATA.mkdir(exist_ok=True)
            report = {"created_at": datetime.now(timezone.utc).isoformat(), "country": snapshot.get("country"), "recommendations": recommendations}
            (DATA / "last_snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
            (DATA / "last_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            self._json(200, report)
        except (UnicodeDecodeError, json.JSONDecodeError, SnapshotError) as exc:
            self._json(400, {"error": f"Не удалось разобрать снимок: {exc}"})

    def log_message(self, fmt: str, *args) -> None:
        print("[ARES] " + fmt % args)


if __name__ == "__main__":
    print(f"ARES AI Bridge: http://{HOST}:{PORT}")
    print("Остановить сервер: Ctrl+C")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        webbrowser.open(f"http://{HOST}:{PORT}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBridge остановлен.")
    finally:
        server.server_close()
