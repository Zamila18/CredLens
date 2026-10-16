"""Tests for the files in deploy/ that can be tested on a laptop.

Owner role: D (full-stack).
Implements: Phase 12 (deployment files, health check that waits for the scorer).

The wait script is tried against a real little HTTP server on this machine (port chosen by the
system), and with a fake clock so no test really waits. Nothing here needs the network.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from dotenv import dotenv_values

from deploy import wait_for_api as wait
from src.config import VALID_MODES

DEPLOY = Path(__file__).resolve().parent.parent / "deploy"
ROOT = DEPLOY.parent


class FakeApi:
    """A tiny server whose /ready answer the test can change."""

    def __init__(self) -> None:
        self.status = 200
        self.body: bytes = b"{}"
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - the name http.server looks for
                self.send_response(outer.status if self.path == "/ready" else 404)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(outer.body)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture()
def api():
    fake = FakeApi()
    yield fake
    fake.stop()


# --- asking once -------------------------------------------------------------------------


def test_one_question_tells_ready_from_not_ready_from_not_answering(api):
    api.status, api.body = 200, json.dumps({"ready": True, "model_version": "v1"}).encode()
    assert wait.ask_ready(api.url) == ("ready", {"ready": True, "model_version": "v1"})
    api.status, api.body = 503, json.dumps({"ready": False, "problems": ["no scorer"]}).encode()
    assert wait.ask_ready(api.url) == ("not_ready", {"ready": False, "problems": ["no scorer"]})
    api.status, api.body = 503, b"<html>bad gateway</html>"  # for example Nginx answering
    assert wait.ask_ready(api.url) == ("not_ready", {})
    api.status = 500
    assert wait.ask_ready(api.url)[0] == "not_answering"
    api.stop()
    assert wait.ask_ready(api.url) == ("not_answering", {})


def test_a_path_that_is_not_ready_is_not_taken_for_ready(api):
    # Another service answering 404 on /ready (wrong port) is not "ready"
    api.status = 404
    assert wait.ask_ready(api.url)[0] == "not_answering"


# --- waiting -----------------------------------------------------------------------------


class Clock:
    """Time that moves only when the script sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.said: list[str] = []

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def run(answers: list[tuple[str, dict]], timeout: float = 60, interval: float = 3):
    clock = Clock()
    queue = iter(answers)
    result = wait.wait_for_api(
        "http://x",
        timeout=timeout,
        interval=interval,
        ask=lambda url: next(queue, answers[-1]),
        sleep=clock.sleep,
        clock=clock,
        say=clock.said.append,
    )
    return result, clock


def test_it_waits_through_the_start_up_and_then_says_ready():
    starting = ("not_answering", {})
    ready = ("ready", {"model_version": "synthetic_bd-v1"})
    result, clock = run([starting] * 8 + [ready])
    assert result is True
    assert clock.said[-1] == "READY after 24 s. Model version: synthetic_bd-v1"
    assert sum("not answering yet" in line for line in clock.said) == 8


def test_it_reports_why_the_api_is_not_ready_once_and_not_on_every_try():
    broken = ("not_ready", {"problems": ["The scorer is not ready."]})
    result, clock = run([broken] * 5 + [("ready", {})])
    assert result is True
    assert sum("not ready: The scorer is not ready." in line for line in clock.said) == 1


def test_it_gives_up_at_the_time_limit_and_names_where_to_look():
    result, clock = run([("not_answering", {})], timeout=30, interval=3)
    assert result is False
    assert clock.now <= 30
    assert "journalctl -u credlens-api" in clock.said[-1]
    assert "python -m src.api.preflight --server" in clock.said[-1]


def test_it_never_waits_longer_than_the_limit_even_with_a_long_interval():
    result, clock = run([("not_answering", {})], timeout=10, interval=7)
    assert result is False and clock.now <= 10


def test_the_command_line_exit_code(api, capsys):
    api.status, api.body = 200, json.dumps({"ready": True, "model_version": "v9"}).encode()
    assert wait.main(["--url", api.url, "--timeout", "5", "--interval", "0.1"]) == 0
    assert "READY" in capsys.readouterr().out
    api.status, api.body = 503, json.dumps({"problems": ["The scorer is not ready."]}).encode()
    assert wait.main(["--url", api.url, "--timeout", "0.5", "--interval", "0.1"]) == 1
    assert "NOT READY" in capsys.readouterr().out


# --- the .env template -------------------------------------------------------------------


def test_the_env_template_has_no_real_values_and_only_settings_the_code_reads():
    values = dotenv_values(DEPLOY / "env.template")
    assert set(values) == {
        "CREDLENS_ENV",
        "CREDLENS_DATA_MODE",
        "CREDLENS_CORS_ORIGINS",
        "DATABASE_URL",
    }
    assert values["CREDLENS_ENV"] == "production"
    assert values["CREDLENS_DATA_MODE"] == "synthetic_bd" and "synthetic_bd" in VALID_MODES
    assert values["CREDLENS_CORS_ORIGINS"] == ""  # same address for the site and the API
    assert values["DATABASE_URL"] == ""  # no address, no password in a committed file
    text = (DEPLOY / "env.template").read_text(encoding="utf-8")
    assert "postgresql" not in text.split("DATABASE_URL")[1].splitlines()[0]
    assert "chmod 600" in text


def test_the_real_env_file_is_ignored_by_git():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in [line.strip() for line in ignored]
