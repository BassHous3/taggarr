"""
Taggarr UI Server
-----------------
Serves the web UI and provides API endpoints for the browser.
Communicates with the already-running main.py process via two files:

  .taggarr_scan_trigger  – server.py creates this to request a scan;
                           main.py deletes it once the scan starts
  .taggarr_state         – main.py writes "scanning" or "idle" here;
                           server.py reads it for /api/status

Log streaming works by tailing the most recent .log file in LOG_PATH,
which is the same file main.py (and Docker) writes to. No subprocess is
spawned — there is always exactly one scan process (main.py).

Endpoints:
  GET  /                  -> taggarr_ui.html
  GET  /api/data          -> taggarr.json (live, no-cache)
  GET  /api/status        -> { "scanning": bool, "version": str }
  POST /api/scan          -> drops trigger file, returns immediately
  GET  /api/logs/stream   -> Server-Sent Events, one JSON obj per log line

Environment variables (shared with main.py via .env / Docker):
  UI_ENABLED   - "true" / "false"  (default: true)
  UI_PORT      - integer            (default: 7879)
  ROOT_TV_PATH - path mounted into container (e.g. /tv)
  LOG_PATH     - directory main.py writes .log files to (default: /logs)
"""

import os
import re
import sys
import json
import time
import queue
import logging
import threading
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, send_from_directory, abort

load_dotenv()

# Config
UI_PORT      = int(os.getenv("UI_PORT", 7879))
UI_ENABLED   = os.getenv("UI_ENABLED", "true").lower() == "true"
ROOT_TV_PATH = os.getenv("ROOT_TV_PATH", "/tv")
LOG_PATH     = os.getenv("LOG_PATH", "/logs")

TAGGARR_JSON = os.path.join(ROOT_TV_PATH, "taggarr.json")
TRIGGER_FILE = os.path.join(ROOT_TV_PATH, ".taggarr_scan_trigger")
STATE_FILE   = os.path.join(ROOT_TV_PATH, ".taggarr_state")
HERE         = Path(__file__).parent.resolve()

# Version
def _read_version():
    try:
        for line in (HERE / "main.py").read_text().splitlines():
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return "unknown"

VERSION = _read_version()

# State (read from file written by main.py)
def is_scanning():
    try:
        return Path(STATE_FILE).read_text().strip() == "scanning"
    except Exception:
        return False

# Log-line parser — matches main.py format: "2025-04-18 14:22:01,123 - INFO - msg"
_LOG_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2} (\d{2}:\d{2}:\d{2}),\d+ - (DEBUG|INFO|WARNING|ERROR|CRITICAL) - (.+)$"
)

def _parse_log_line(raw):
    m = _LOG_RE.match(raw.rstrip())
    if not m:
        return None
    return {"time": m.group(1), "level": m.group(2), "msg": m.group(3)}

# SSE broadcast
_subscribers = []
_sub_lock = threading.Lock()

def _broadcast(payload):
    with _sub_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)

def _broadcast_dict(d):
    _broadcast(json.dumps(d))

def _broadcast_line(raw):
    parsed = _parse_log_line(raw)
    if parsed:
        _broadcast_dict(parsed)

# Log file tailer + state watcher
def _find_latest_log():
    try:
        logs = sorted(Path(LOG_PATH).glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        return logs[0] if logs else None
    except Exception:
        return None

def _tail_logs():
    current_path = None
    fh = None
    last_check   = 0.0
    was_scanning = False

    while True:
        try:
            now = time.monotonic()

            # Detect scan finishing -> send sentinel to browser
            currently_scanning = is_scanning()
            if was_scanning and not currently_scanning:
                _broadcast_dict({
                    "time":  datetime.now().strftime("%H:%M:%S"),
                    "level": "INFO",
                    "msg":   "\u3014scan process exited\u3015",
                })
            was_scanning = currently_scanning

            # Check for newer log file every 5 s
            if now - last_check > 5:
                latest = _find_latest_log()
                last_check = now
                if latest and latest != current_path:
                    if fh:
                        fh.close()
                    current_path = latest
                    fh = open(current_path, "r", encoding="utf-8", errors="replace")
                    fh.seek(0, 2)  # tail — only new lines

            # Drain new lines
            if fh:
                line = fh.readline()
                if line:
                    _broadcast_line(line)
                    continue

        except Exception:
            fh = None
            current_path = None

        time.sleep(0.2)

threading.Thread(target=_tail_logs, daemon=True).start()

# Flask app
app = Flask(__name__, static_folder=None)

# Silence Werkzeug access log — it clutters Docker logs
logging.getLogger("werkzeug").setLevel(logging.ERROR)

@app.route("/")
def index():
    if not (HERE / "taggarr_ui.html").exists():
        abort(404, description="taggarr_ui.html not found")
    resp = send_from_directory(str(HERE), "taggarr_ui.html")
    resp.headers["Cache-Control"] = "no-store"
    return resp

@app.route("/api/data")
def api_data():
    if not os.path.exists(TAGGARR_JSON):
        return jsonify({"version": VERSION, "series": {}})
    with open(TAGGARR_JSON, "r", encoding="utf-8") as f:
        raw = f.read()
    return Response(raw, mimetype="application/json",
                    headers={"Cache-Control": "no-store"})

@app.route("/api/status")
def api_status():
    return jsonify({"scanning": is_scanning(), "version": VERSION})

@app.route("/api/scan", methods=["POST"])
def api_scan():
    if is_scanning():
        return jsonify({"ok": False, "reason": "Scan already in progress"}), 409
    try:
        Path(TRIGGER_FILE).touch()
    except Exception as e:
        return jsonify({"ok": False, "reason": f"Could not write trigger file: {e}"}), 500
    return jsonify({"ok": True})

@app.route("/api/logs/stream")
def api_logs_stream():
    q = queue.Queue(maxsize=500)
    with _sub_lock:
        _subscribers.append(q)

    def event_stream():
        yield "event: ping\ndata: {}\n\n"
        try:
            while True:
                try:
                    payload = q.get(timeout=25)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
        except GeneratorExit:
            pass
        finally:
            with _sub_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return Response(
        event_stream(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# Entry point
if __name__ == "__main__":
    if not UI_ENABLED:
        print("UI_ENABLED=false - server.py exiting.")
        sys.exit(0)

    from werkzeug.serving import make_server
    print(f"Taggarr UI -> http://0.0.0.0:{UI_PORT}")
    srv = make_server("0.0.0.0", UI_PORT, app, threaded=True)
    srv.serve_forever()