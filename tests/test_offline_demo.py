"""Tests for the offline demo server (deploy/offline_demo.py).

Owner role: D (full-stack).
Implements: Phase 12 (offline fallback).

The server is tried for real on this machine: a stand-in "API" records what it is sent, a
small built dashboard sits in a temporary folder, and requests go through the handler.
No network, no Docker, no real API.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from pathlib import Path

import pytest

from deploy import offline_demo

ROOT = Path(__file__).resolve().parent.parent

INDEX = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500&display=swap"
      rel="stylesheet"
    />
    <title>CredLens</title>
    <script type="module" crossorigin src="/assets/index-abc.js"></script>
    <link rel="stylesheet" crossorigin href="/assets/index-abc.css">
  </head>
  <body><div id="root"></div></body>
</html>
"""


class FakeApi:
    """A stand-in API: remembers the last request, answers with what the test sets."""

    def __init__(self) -> None:
        self.status = 200
        self.reply = b'{"ok": true}'
        self.seen: dict = {}
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def handle_any(self):
                length = int(self.headers.get("Content-Length") or 0)
                outer.seen = {
                    "method": self.command,
                    "path": self.path,
                    "body": self.rfile.read(length) if length else b"",
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                }
                self.send_response(outer.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Secret-Internal", "must not reach the browser")
                self.end_headers()
                self.wfile.write(outer.reply)

            do_GET = do_POST = handle_any  # noqa: N815

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def site(tmp_path):
    """(base url of the offline server, the fake API)."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(INDEX, encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (dist / "assets" / "index-abc.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "assets" / "index-abc.css").write_text("body{}", encoding="utf-8")
    (dist / ".env").write_text("SECRET=1", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("not the dashboard's", encoding="utf-8")
    api = FakeApi()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), offline_demo.make_handler(dist, api.url)
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}", api
    server.shutdown()
    server.server_close()
    api.stop()


def fetch(url: str, headers=None, data: bytes | None = None, method: str | None = None):
    request = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


# --- the dashboard -----------------------------------------------------------------------


def test_the_dashboard_is_served_without_the_lines_that_ask_google_for_fonts(site):
    base, _ = site
    status, headers, body = fetch(base + "/")
    page = body.decode("utf-8")
    assert status == 200 and "text/html" in headers["Content-Type"]
    assert "fonts.googleapis.com" not in page and "fonts.gstatic.com" not in page
    assert '<div id="root">' in page
    assert 'src="/assets/index-abc.js"' in page and 'href="/assets/index-abc.css"' in page
    assert 'href="/favicon.svg"' in page  # only the font lines are gone


def test_a_dashboard_address_opens_the_dashboard_and_a_built_file_is_sent_as_it_is(site):
    base, _ = site
    for path in ("/merchants/M000031", "/audit", "/decisions", "/index.html"):
        status, _, body = fetch(base + path)
        assert status == 200 and b'id="root"' in body, path
    status, headers, body = fetch(base + "/assets/index-abc.js")
    assert (status, body) == (200, b"console.log(1)")
    assert "javascript" in headers["Content-Type"]
    assert "css" in fetch(base + "/assets/index-abc.css")[1]["Content-Type"]
    assert fetch(base + "/favicon.svg")[0] == 200


def test_a_missing_built_file_is_a_404_not_the_dashboard(site):
    base, _ = site
    status, _, body = fetch(base + "/assets/gone.js")
    assert status == 404 and b'id="root"' not in body


@pytest.mark.parametrize(
    "path", ["/.env", "/assets/../.env", "/%2e%2e/outside.txt", "/..%2foutside.txt", "/%2e%2e%2f"]
)
def test_hidden_files_and_paths_outside_the_dashboard_are_never_served(site, path):
    base, _ = site
    status, _, body = fetch(base + path)
    assert b"SECRET" not in body and b"not the dashboard" not in body
    assert status in (200, 404)  # 200 only with the dashboard page itself
    if status == 200:
        assert b'id="root"' in body


# --- the API behind /api -----------------------------------------------------------------


def test_api_calls_lose_the_prefix_and_keep_the_query_and_the_demo_token(site):
    base, api = site
    status, headers, body = fetch(
        base + "/api/merchants?band=Strong&town_tier=metro",
        {"X-Demo-Token": "officer-1", "Cookie": "private=1", "Authorization": "Basic abc"},
    )
    assert status == 200 and json.loads(body) == {"ok": True}
    assert api.seen["path"] == "/merchants?band=Strong&town_tier=metro"
    assert api.seen["headers"]["x-demo-token"] == "officer-1"
    assert "cookie" not in api.seen["headers"] and "authorization" not in api.seen["headers"]
    assert headers["Cache-Control"] == "no-store"
    assert "X-Secret-Internal" not in headers  # only chosen headers go back


def test_a_post_with_a_body_reaches_the_api_unchanged(site):
    base, api = site
    payload = json.dumps({"officer_action": "override_up", "reason_text": "Visited ✓"}).encode()
    status, _, _ = fetch(
        base + "/api/merchants/M000031/decision",
        {"X-Demo-Token": "officer-2", "Content-Type": "application/json"},
        payload,
        "POST",
    )
    assert status == 200
    assert (api.seen["method"], api.seen["path"]) == ("POST", "/merchants/M000031/decision")
    assert api.seen["body"] == payload
    assert api.seen["headers"]["content-type"] == "application/json"


def test_the_apis_errors_are_passed_on_as_they_are(site):
    base, api = site
    api.status = 403
    error = {"detail": {"code": "consent_required", "message": "Consent needed"}}
    api.reply = json.dumps(error).encode()
    status, _, body = fetch(base + "/api/merchants/M1/score", {"X-Demo-Token": "viewer-1"})
    assert status == 403 and json.loads(body)["detail"]["code"] == "consent_required"


def test_a_stopped_api_gives_a_page_that_reloads_itself_not_a_crash(site):
    base, api = site
    api.stop()
    status, headers, body = fetch(base + "/api/health")
    assert status == 502 and "text/html" in headers["Content-Type"]
    assert b"CredLens is starting" in body and b"refresh" in body


def test_only_get_and_post_are_allowed_on_the_dashboard(site):
    base, _ = site
    assert fetch(base + "/", data=b"x", method="POST")[0] == 405


# --- the real dashboard build and the helpers --------------------------------------------


def test_the_real_index_page_loses_only_the_font_lines():
    index = ROOT / "web" / "index.html"
    text = index.read_text(encoding="utf-8")
    cleaned = offline_demo.local_index(text)
    assert "fonts.g" in text and "fonts.g" not in cleaned
    for kept in ('<div id="root">', 'type="module"', "<title>", 'rel="icon"'):
        assert kept in cleaned
    assert cleaned.count("<link") == text.count("<link") - 3  # two preconnects, one stylesheet


def test_the_script_names_what_is_missing(tmp_path):
    problems = offline_demo.problems_before_start(tmp_path)
    joined = " ".join(problems)
    fixes = ("tasks.py setup", "tasks.py data", "tasks.py train", "npm run build")
    for fix in fixes:
        assert fix in joined
    assert len(problems) == 4


def test_the_python_of_the_virtual_environment_is_found_where_tasks_py_looks():
    tasks = (ROOT / "tasks.py").read_text(encoding="utf-8")
    assert '"Scripts" / "python.exe"' in tasks and '"bin" / "python"' in tasks
    expected = "Scripts" if sys.platform.startswith("win") else "bin"
    assert offline_demo.venv_python(Path("x")).parent.name == expected


def test_stopping_the_api_stops_what_it_started():
    code = (
        "import subprocess, sys, time;"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']);"
        "time.sleep(120)"
    )
    process = subprocess.Popen([sys.executable, "-c", code])
    time.sleep(1)
    offline_demo.stop_process(process)
    assert process.poll() is not None


def test_the_script_listens_on_this_computer_only_and_has_no_password_to_leak():
    source = (ROOT / "deploy" / "offline_demo.py").read_text(encoding="utf-8")
    assert 'ThreadingHTTPServer(("127.0.0.1"' in source
    assert "0.0.0.0" not in source


def test_the_wait_loop_can_be_stopped_with_ctrl_c_on_windows():
    """`threading.Event().wait()` ignores Ctrl+C on Windows; a sleeping loop does not."""
    source = (ROOT / "deploy" / "offline_demo.py").read_text(encoding="utf-8")
    assert "Event().wait()" not in source
    assert "time.sleep(1)" in source and "except KeyboardInterrupt" in source
