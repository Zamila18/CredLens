"""Run the whole CredLens demo on this laptop with no internet: the API and the dashboard.

Purpose: the fallback if the venue's internet fails. One command starts the API (if it is not
    running), waits until it can score, and serves the built dashboard and the API on one local
    address, the way Nginx does on the server. No Node.js, no network, no Docker is needed at
    demo time.
Owner role: D (full-stack).
Implements: Phase 12 (offline fallback), docs/DEPLOY.md part E.

    python deploy/offline_demo.py                 starts everything and opens the browser
    python deploy/offline_demo.py --no-browser    the same, without opening a browser
    python deploy/offline_demo.py --port 9000     another port for the dashboard

Needs, once, BEFORE the event and with internet: `python tasks.py setup`, `python tasks.py data`,
`python tasks.py train`, and the dashboard built (`cd web && npm ci && npm run build`).
Stop it with Ctrl+C (it also stops the API it started).

It listens on 127.0.0.1 only and has no password: it is for this laptop. Standard library only.
The dashboard's page asks Google for its fonts; this server leaves those two lines out, so an
offline page does not wait for a network that is not there. Text then uses the computer's own
fonts (Bangla included).
"""

from __future__ import annotations

import argparse
import mimetypes
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import wait_for_api  # noqa: E402  (the sibling script; it is not a package)

ROOT = HERE.parent
DIST = ROOT / "web" / "dist"
DEFAULT_PORT = 8765
API_HOST, API_PORT = "127.0.0.1", 8000
API_PREFIX = "/api/"
UPSTREAM_TIMEOUT_SECONDS = 120
# Headers a browser sends that the API needs (everything else is left out on purpose).
FORWARDED_REQUEST_HEADERS = ("x-demo-token", "content-type", "accept", "accept-language")
FORWARDED_RESPONSE_HEADERS = ("content-type", "cache-control")
# The lines of index.html that ask Google for fonts.
GOOGLE_FONT_LINE = re.compile(
    r"[ \t]*<link[^>]*fonts\.g(?:oogleapis|static)\.com[^>]*>[ \t]*\r?\n?"
)

STARTING_PAGE = (
    b"<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=5>"
    b"<title>CredLens is starting</title><p style='font:16px system-ui;margin:3rem'>"
    b"CredLens is starting. This page tries again every 5 seconds."
)


def venv_python(root: Path = ROOT) -> Path:
    """The Python inside .venv, as tasks.py finds it."""
    folder = root / ".venv" / ("Scripts" if sys.platform.startswith("win") else "bin")
    return folder / ("python.exe" if sys.platform.startswith("win") else "python")


def local_index(text: str) -> str:
    """index.html without the lines that load fonts from Google."""
    return GOOGLE_FONT_LINE.sub("", text)


def make_handler(dist: Path, api_url: str):
    """A request handler that serves `dist` and passes /api/... to the API at `api_url`."""
    dist = dist.resolve()

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"  # one answer per connection: simple and enough

        def log_message(self, *args):  # keep the terminal quiet
            pass

        def do_GET(self):  # noqa: N802 - the names http.server looks for
            self.route()

        def do_POST(self):  # noqa: N802
            self.route()

        def route(self) -> None:
            parts = urlsplit(self.path)
            if parts.path.startswith(API_PREFIX):
                self.proxy(parts)
            elif self.command == "GET":
                self.static(parts.path)
            else:
                # read what was sent, or the browser sees a broken connection, not our answer
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self.reply(405, b"Method not allowed", "text/plain")

        # --- the API ---------------------------------------------------------------------
        def proxy(self, parts) -> None:
            target = api_url + parts.path[len(API_PREFIX) - 1 :]
            if parts.query:
                target += "?" + parts.query
            headers = {
                name: value
                for name, value in self.headers.items()
                if name.lower() in FORWARDED_REQUEST_HEADERS
            }
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            request = urllib.request.Request(
                target, data=body, headers=headers, method=self.command
            )
            try:
                with urllib.request.urlopen(request, timeout=UPSTREAM_TIMEOUT_SECONDS) as answer:
                    status, got, content = answer.status, answer.headers, answer.read()
            except urllib.error.HTTPError as error:
                status, got, content = error.code, error.headers, error.read()
            except (urllib.error.URLError, OSError):
                self.reply(502, STARTING_PAGE, "text/html; charset=utf-8")
                return
            self.send_response(status)
            for name in FORWARDED_RESPONSE_HEADERS:
                if got.get(name):
                    self.send_header(name, got[name])
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        # --- the dashboard ---------------------------------------------------------------
        def static(self, url_path: str) -> None:
            relative = unquote(url_path).lstrip("/")
            wanted = (dist / relative).resolve()
            hidden = any(part.startswith(".") for part in Path(relative).parts)
            inside = wanted == dist or dist in wanted.parents
            if hidden or not inside:
                self.reply(404, b"Not found", "text/plain")
            elif wanted.is_file() and wanted.name != "index.html":
                kind = mimetypes.guess_type(wanted.name)[0] or "application/octet-stream"
                self.reply(200, wanted.read_bytes(), kind)
            elif relative.startswith("assets/"):
                self.reply(404, b"Not found", "text/plain")  # a missing built file is no page
            else:  # a dashboard address: give the one-page app
                page = local_index((dist / "index.html").read_text(encoding="utf-8"))
                self.reply(200, page.encode("utf-8"), "text/html; charset=utf-8")

        def reply(self, status: int, body: bytes, kind: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def problems_before_start(root: Path = ROOT) -> list[str]:
    """What is missing on this laptop, in plain words (empty: ready to go)."""
    found = []
    if not venv_python(root).exists():
        found.append("Python packages are not installed. Run: python tasks.py setup")
    if not (root / "data" / "app.db").exists():
        found.append("There is no database yet. Run: python tasks.py data")
    if not (root / "src" / "model" / "artifacts" / "synthetic_bd" / "model.joblib").exists():
        found.append("There is no trained model yet. Run: python tasks.py train")
    if not (root / "web" / "dist" / "index.html").exists():
        found.append(
            "The dashboard is not built. Run (needs internet, once): "
            "cd web && npm ci && npm run build"
        )
    return found


def api_is_ready(url: str) -> bool:
    return wait_for_api.ask_ready(url)[0] == "ready"


def start_api(root: Path = ROOT) -> subprocess.Popen:
    """Start the API the way `python tasks.py api` does; its log goes to data/."""
    log = open(root / "data" / "offline_demo_api.log", "w", encoding="utf-8")
    command = [str(venv_python(root)), "-m", "uvicorn", "src.api.main:app"]
    command += ["--host", API_HOST, "--port", str(API_PORT)]
    return subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)


def stop_process(process: subprocess.Popen) -> None:
    """Stop the API and everything it started. On Windows the .venv's python.exe is only a
    launcher for the real one, so the whole tree has to go or the API keeps running."""
    if sys.platform.startswith("win"):
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the CredLens demo with no internet.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    missing = problems_before_start()
    if missing:
        print("Not ready:\n  " + "\n  ".join(missing))
        return 1

    api_url = f"http://{API_HOST}:{API_PORT}"
    started: subprocess.Popen | None = None
    if api_is_ready(api_url):
        print("The API is already running on this laptop: using it.")
    else:
        print("Starting the API (30 to 60 seconds) ...")
        (ROOT / "data").mkdir(exist_ok=True)
        started = start_api()
        if not wait_for_api.wait_for_api(api_url, timeout=240):
            print("The API did not become ready. See data/offline_demo_api.log")
            stop_process(started)
            return 1

    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(DIST, api_url))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    address = f"http://localhost:{args.port}/"
    print(f"\nCredLens is running, offline, at {address}")
    print("Synthetic demo data. Decision support only. Stop with Ctrl+C.")
    if not args.no_browser:
        webbrowser.open(address)
    try:
        while True:  # a sleeping loop: waiting on an Event cannot be stopped with Ctrl+C on Windows
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        server.shutdown()
        if started is not None:
            stop_process(started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
