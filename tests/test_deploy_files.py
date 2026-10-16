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


# --- the Nginx config (the Docker test, deploy/test_nginx_local.py, runs it for real) -----

NGINX = (DEPLOY / "nginx" / "credlens.conf").read_text(encoding="utf-8")


def block(text: str, header: str) -> str:
    """The text between the braces that follow `header` (the config has no nested blocks
    inside the ones read here)."""
    start = text.index(header)
    opening = text.index("{", start)
    depth, position = 0, opening
    while True:
        depth += {"{": 1, "}": -1}.get(text[position], 0)
        if depth == 0:
            return text[opening + 1 : position]
        position += 1


def test_the_nginx_file_is_balanced_and_the_site_is_behind_a_password():
    assert NGINX.count("{") == NGINX.count("}")
    server = block(NGINX, "server {")
    lines = [line.strip() for line in server.splitlines()]  # a commented-out line is no line
    assert any(line.startswith('auth_basic "') for line in lines)
    assert "auth_basic_user_file /etc/nginx/credlens.htpasswd;" in lines
    assert "server_tokens off;" in lines
    assert "location /api/" in server and "location /assets/" in server


def test_the_api_is_passed_on_with_the_prefix_off_and_the_password_kept_from_it():
    api = block(NGINX, "location /api/ {")
    # a trailing slash on both sides is what removes "/api"
    assert "proxy_pass http://127.0.0.1:8000/;" in api
    assert 'proxy_set_header Authorization "";' in api
    for header in ("Host", "X-Real-IP", "X-Forwarded-For", "X-Forwarded-Proto"):
        assert f"proxy_set_header {header} " in api
    assert 'add_header Cache-Control "no-store" always;' in api
    # add_header in a location replaces the server's, so the important ones are repeated
    for header in ("X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"):
        assert f"add_header {header} " in api
    assert "0.0.0.0" not in NGINX  # the API is never named by anything but the loopback address


def test_the_dashboards_api_prefix_is_the_one_nginx_serves():
    client = (ROOT / "web" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    assert "?? '/api'" in client
    vite = (ROOT / "web" / "vite.config.ts").read_text(encoding="utf-8")
    assert "'/api'" in vite and r"replace(/^\/api/, '')" in vite  # the same job as Nginx's


def test_the_nginx_file_allows_the_largest_import_and_no_more_than_needed():
    from src.api.importer import MAX_IMPORT_BYTES

    size = int(NGINX.split("client_max_body_size ")[1].split("m;")[0]) * 1024 * 1024
    assert MAX_IMPORT_BYTES < size <= 2 * MAX_IMPORT_BYTES


def test_the_dashboard_is_a_one_page_app_and_built_files_are_cached_for_good():
    assert "try_files $uri /index.html;" in block(NGINX, "location / {")
    assets = block(NGINX, "location /assets/ {")
    assert "try_files $uri =404;" in assets  # a missing built file is not the dashboard
    assert "max-age=31536000" in assets and "immutable" in assets
    assert "expires" not in assets  # `expires` would add a second Cache-Control header
    assert "no-cache" in block(NGINX, "location = /index.html {")
    assert r"location ~ /\." in NGINX and "deny all;" in NGINX


def test_a_flood_is_answered_429_so_it_is_not_mistaken_for_the_starting_page():
    assert "limit_req_status 429;" in NGINX
    assert "limit_req_zone $binary_remote_addr" in NGINX
    assert "error_page 502 503 504 /starting.html;" in NGINX


def test_the_starting_page_exists_reloads_itself_and_promises_nothing_wrong():
    page = (DEPLOY / "nginx" / "starting.html").read_text(encoding="utf-8")
    assert 'http-equiv="refresh"' in page and "CredLens is starting" in page
    assert "Decision support only" in page
    for word in ("approved", "declined", "eligible"):
        assert word not in page.lower()
    assert "/opt/credlens/deploy/nginx" in NGINX


def test_the_security_headers_are_on_the_page():
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Content-Security-Policy",
    ):
        assert f"add_header {header} " in block(NGINX, "server {")
    index = block(NGINX, "location = /index.html {")
    assert "Content-Security-Policy" in index and "frame-ancestors 'none'" in index


# --- the systemd service ------------------------------------------------------------------

SERVICE = (DEPLOY / "credlens-api.service").read_text(encoding="utf-8")


def service_lines() -> list[str]:
    return [line.strip() for line in SERVICE.splitlines() if line.strip()]


def test_the_service_runs_the_api_on_the_loopback_address_only_as_its_own_user():
    lines = service_lines()
    start = next(line for line in lines if line.startswith("ExecStart="))
    assert "-m uvicorn src.api.main:app" in start
    assert "--host 127.0.0.1 --port 8000" in start  # the same address Nginx proxies to
    assert "--workers 1" in start and "0.0.0.0" not in SERVICE
    assert "proxy_pass http://127.0.0.1:8000/;" in NGINX
    assert "User=credlens" in lines and "Group=credlens" in lines
    assert "User=root" not in lines
    assert "WorkingDirectory=/opt/credlens" in lines


def test_the_service_reads_the_env_file_and_waits_for_the_scorer_before_it_counts_as_started():
    lines = service_lines()
    assert "EnvironmentFile=/opt/credlens/.env" in lines
    post = next(line for line in lines if line.startswith("ExecStartPost="))
    assert "/opt/credlens/deploy/wait_for_api.py" in post
    timeout = int(post.split("--timeout ")[1].split()[0])
    startup = int(next(line for line in lines if line.startswith("TimeoutStartSec=")).split("=")[1])
    assert timeout < startup  # the wait gives up first, with its own message
    assert "Restart=on-failure" in lines and "WantedBy=multi-user.target" in lines


def test_the_service_may_write_only_its_data_folder():
    lines = service_lines()
    for setting in ("NoNewPrivileges=true", "PrivateTmp=true", "ProtectSystem=strict"):
        assert setting in lines
    assert "ReadWritePaths=/opt/credlens/data" in lines
    assert "PYTHONDONTWRITEBYTECODE=1" in SERVICE.replace("Environment=", "")


def test_the_service_nginx_and_env_template_agree_on_where_the_project_lives():
    assert "root /opt/credlens/web/dist;" in NGINX
    assert "/opt/credlens/deploy/nginx" in NGINX
    template = (DEPLOY / "env.template").read_text(encoding="utf-8")
    assert "/opt/credlens/.env" in template


# --- the upload bundle --------------------------------------------------------------------


@pytest.fixture()
def project(tmp_path):
    """A small project folder: built dashboard, trained model, written model card."""
    (tmp_path / "web" / "dist" / "assets").mkdir(parents=True)
    (tmp_path / "web" / "dist" / "index.html").write_text("<div id=root>", encoding="utf-8")
    (tmp_path / "web" / "dist" / "assets" / "app.js").write_text("x", encoding="utf-8")
    model = tmp_path / "src" / "model" / "artifacts" / "synthetic_bd"
    model.mkdir(parents=True)
    (model / "model.joblib").write_bytes(b"model")
    (model / "metadata.json").write_text('{"version_id": "v1"}', encoding="utf-8")
    (model.parent / "other_mode").mkdir()
    (model.parent / "other_mode" / "model.joblib").write_bytes(b"not for the server")
    card = tmp_path / "reports" / "synthetic_bd"
    card.mkdir(parents=True)
    (card / "model_card.json").write_text('{"model_version": "v1"}', encoding="utf-8")
    return tmp_path


def test_the_bundle_holds_the_dashboard_and_the_model_and_nothing_else(project, tmp_path):
    import tarfile

    from deploy import make_bundle

    output = tmp_path / "out.tar.gz"
    names = make_bundle.make_bundle(project, output)
    assert sorted(names) == [
        "src/model/artifacts/synthetic_bd/metadata.json",
        "src/model/artifacts/synthetic_bd/model.joblib",
        "web/dist/assets/app.js",
        "web/dist/index.html",
    ]
    with tarfile.open(output) as archive:
        assert sorted(archive.getnames()) == sorted(names)
        member = archive.getmember("src/model/artifacts/synthetic_bd/model.joblib")
        assert archive.extractfile(member).read() == b"model"


def test_the_bundle_refuses_a_model_the_card_was_not_written_for(project, tmp_path):
    from deploy import make_bundle

    card = project / "reports" / "synthetic_bd" / "model_card.json"
    card.write_text('{"model_version": "older"}', encoding="utf-8")
    with pytest.raises(make_bundle.BundleError, match="written for older"):
        make_bundle.make_bundle(project, tmp_path / "out.tar.gz")
    assert len(make_bundle.make_bundle(project, tmp_path / "o.tar.gz", allow_other_model=True)) == 4
    card.unlink()
    with pytest.raises(make_bundle.BundleError, match="written for None"):
        make_bundle.make_bundle(project, tmp_path / "out.tar.gz")


def test_the_bundle_refuses_when_something_is_missing(project, tmp_path):
    from deploy import make_bundle

    (project / "src" / "model" / "artifacts" / "synthetic_bd" / "metadata.json").unlink()
    with pytest.raises(make_bundle.BundleError, match="No trained model"):
        make_bundle.make_bundle(project, tmp_path / "out.tar.gz")
    (project / "web" / "dist" / "index.html").unlink()
    with pytest.raises(make_bundle.BundleError, match="not built"):
        make_bundle.make_bundle(project, tmp_path / "out.tar.gz")


def test_the_bundle_command_says_what_it_did_and_its_exit_code(
    project, tmp_path, monkeypatch, capsys
):
    from deploy import make_bundle

    monkeypatch.setattr(make_bundle, "ROOT", project)
    output = tmp_path / "pack.tar.gz"
    assert make_bundle.main(["--output", str(output)]) == 0
    assert "model v1" in capsys.readouterr().out and output.exists()
    (project / "web" / "dist" / "index.html").unlink()
    assert make_bundle.main(["--output", str(output)]) == 1
    assert "NOT PACKED" in capsys.readouterr().out


def test_a_bundle_is_never_committed():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "credlens-upload.tar.gz" in ignored or "*.tar.gz" in ignored


# --- the deployment guide -----------------------------------------------------------------

GUIDE = (ROOT / "docs" / "DEPLOY.md").read_text(encoding="utf-8")


def test_the_guide_uses_every_file_in_deploy():
    for name in (
        "credlens-api.service",
        "env.template",
        "wait_for_api.py",
        "make_bundle.py",
        "offline_demo.py",
        "test_nginx_local.py",
        "nginx/credlens.conf",
    ):
        assert name in GUIDE, f"docs/DEPLOY.md never mentions {name}"
        assert (DEPLOY / name).exists(), name


def test_every_script_the_guide_runs_exists():
    import re

    for path in re.findall(r"python3? (deploy/[\w/]+\.py|/opt/credlens/deploy/[\w/]+\.py)", GUIDE):
        assert (ROOT / path.replace("/opt/credlens/", "")).exists(), path
    for module in re.findall(r"-m ((?:src)\.[\w.]+)", GUIDE):
        assert (ROOT / (module.replace(".", "/") + ".py")).exists(), module


def test_the_guide_and_the_service_use_the_same_names():
    assert "systemctl enable --now credlens-api" in GUIDE
    assert "journalctl -u credlens-api" in GUIDE
    wait = (DEPLOY / "wait_for_api.py").read_text(encoding="utf-8")
    assert "journalctl -u credlens-api" in wait  # the hint the script prints is a real command
    assert "Ubuntu 22.04" in GUIDE  # the Python version we tested on
    assert "never run `python tasks.py train`" in GUIDE.lower().replace("**", "")


def test_nothing_in_deploy_or_the_guide_holds_a_secret():
    import re

    texts = {"guide": GUIDE}
    for path in DEPLOY.rglob("*"):
        if path.is_file() and path.suffix in {".py", ".conf", ".service", ".template", ".html"}:
            texts[path.name] = path.read_text(encoding="utf-8")
    for name, text in texts.items():
        # an address with a user name and a password in it, a key, or a token
        assert not re.search(r"://[^/\s:@]+:[^@\s]+@", text), name
        assert "BEGIN PRIVATE KEY" not in text and "ghp_" not in text, name
