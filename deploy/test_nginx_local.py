"""Try the real Nginx config on this laptop, in Docker, before it goes on a server.

Purpose: the server's Nginx file (deploy/nginx/credlens.conf) is used exactly as it is, with
    only the address of the API changed to this laptop. The built dashboard (web/dist) and the
    running API are served the way the server will serve them.
Owner role: D (full-stack).
Implements: Phase 12 ("test the built dashboard served the way the server will serve it").

Before you run it:
  1. Docker Desktop is running (the whale icon says "Engine running").
  2. The dashboard is built:   cd web && npm ci && npm run build
  3. The API is running:       python tasks.py api   (then: python deploy/wait_for_api.py)
     Without the API the checks that need it are skipped and said so.

    python deploy/test_nginx_local.py                 run the checks, then clean up
    python deploy/test_nginx_local.py --keep-running  leave the site on http://localhost:8080
                                                      (user: demo, password: demo-test)
    stop it later with:        docker rm -f credlens-nginx-site

The first run downloads the official nginx image (about 20 MB). Everything listens on
127.0.0.1 only. The test password is for this laptop test only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONF = ROOT / "deploy" / "nginx" / "credlens.conf"
STARTING = ROOT / "deploy" / "nginx" / "starting.html"
DIST = ROOT / "web" / "dist"

IMAGE = "nginx:1.26-alpine"
API_PORT = 8000
ECHO_PORT = 8090
USER, PASSWORD = "demo", "demo-test"
UPSTREAM = "http://127.0.0.1:8000/"
# container name -> port on this laptop
SITE, ECHO, DEAD = "credlens-nginx-site", "credlens-nginx-echo", "credlens-nginx-dead"
PORTS = {SITE: 8080, ECHO: 8082, DEAD: 8081}
MEGABYTE = 1024 * 1024


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=check)


def basic(user: str = USER, password: str = PASSWORD) -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def get(url, headers=None, data=None, method=None):
    """(status, headers, body) of one request. HTTP errors are answers, not exceptions."""
    request = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.headers, error.read()


class Echo(BaseHTTPRequestHandler):
    """A stand-in API that remembers what Nginx sent it."""

    seen: dict = {}

    def do_GET(self):  # noqa: N802 - the name http.server looks for
        headers = {key.lower(): value for key, value in self.headers.items()}
        Echo.seen = {"path": self.path, "headers": headers}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


class Report:
    def __init__(self) -> None:
        self.failed = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        print(f"[{'OK  ' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"        got: {detail}")
            self.failed += 1


def write_config(folder: Path, upstream_port: int, name: str) -> Path:
    """The real config with only the API's address changed (a container reaches this
    laptop as host.docker.internal)."""
    text = CONF.read_text(encoding="utf-8")
    assert UPSTREAM in text, "credlens.conf no longer proxies to 127.0.0.1:8000"
    path = folder / f"{name}.conf"
    path.write_text(
        text.replace(UPSTREAM, f"http://host.docker.internal:{upstream_port}/"), encoding="utf-8"
    )
    return path


def mounts(conf: Path, htpasswd: Path) -> list[str]:
    pairs = [
        (conf, "/etc/nginx/conf.d/default.conf"),
        (htpasswd, "/etc/nginx/credlens.htpasswd"),
        (DIST, "/opt/credlens/web/dist"),
        (STARTING, "/opt/credlens/deploy/nginx/starting.html"),
    ]
    return [arg for src, dst in pairs for arg in ("-v", f"{src.resolve().as_posix()}:{dst}:ro")]


def start(name: str, conf: Path, htpasswd: Path) -> None:
    docker("rm", "-f", name, check=False)
    docker(
        "run", "-d", "--name", name, "-p", f"127.0.0.1:{PORTS[name]}:80",
        "--add-host", "host.docker.internal:host-gateway", *mounts(conf, htpasswd), IMAGE,
    )  # fmt: skip


def wait_until_up(url: str, seconds: int = 20) -> None:
    end = time.time() + seconds
    while time.time() < end:
        try:
            get(url)
            return
        except OSError:
            time.sleep(0.5)


def port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def check_password(r: Report, site: str) -> None:
    status, headers, _ = get(site + "/")
    asks = "Basic" in headers.get("WWW-Authenticate", "")
    r.check("the site asks for a password", status == 401 and asks, str(status))
    r.check("a wrong password is refused", get(site + "/", basic(USER, "wrong"))[0] == 401)
    r.check("the API is behind the password too", get(site + "/api/health")[0] == 401)


def check_dashboard(r: Report, site: str) -> None:
    status, headers, body = get(site + "/", basic())
    r.check("the dashboard is served", status == 200 and b'id="root"' in body, str(status))
    r.check("Nginx hides its version", headers.get("Server") == "nginx", str(headers.get("Server")))
    for name, expected in (
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
    ):
        r.check(f"header {name} on the page", headers.get(name) == expected, str(headers.get(name)))
    csp = headers.get("Content-Security-Policy", "")
    r.check("a content security policy", "default-src 'self'" in csp and "frame-ancestors" in csp)
    r.check("the page is asked for again each time", "no-cache" in headers.get("Cache-Control", ""))

    for path in ("/merchants/M000031", "/audit", "/consent"):
        status, _, body = get(site + path, basic())
        ok = status == 200 and b'id="root"' in body
        r.check(f"{path} opens the dashboard (one-page app)", ok, str(status))

    asset = next((DIST / "assets").glob("*.js"), None)
    if asset is not None:
        status, headers, _ = get(site + f"/assets/{asset.name}", basic())
        cache = headers.get("Cache-Control", "")
        r.check("a built file is kept for a year", status == 200 and "immutable" in cache, cache)
    status, _, body = get(site + "/assets/missing-file.js", basic())
    r.check("a missing built file is 404, not the dashboard", status == 404, str(status))
    for hidden in ("/.env", "/.git/config", "/assets/.env"):
        r.check(f"{hidden} is never served", get(site + hidden, basic())[0] == 404)


def check_api(r: Report, site: str) -> None:
    status, headers, body = get(site + "/api/health", basic())
    r.check("/api/health reaches the API", status == 200 and b"Decision support only" in body)
    r.check("API answers are not kept", "no-store" in headers.get("Cache-Control", ""))
    status, _, body = get(site + "/api/ready", basic())
    r.check("/api/ready reaches the API", status == 200 and json.loads(body).get("ready") is True)
    status, _, body = get(site + "/api/merchants", basic())
    code = json.loads(body).get("detail", {}).get("code") if status == 401 else None
    r.check("the API's own sign-in still works behind the password", code == "missing_token")
    status, _, body = get(site + "/api/merchants", {**basic(), "X-Demo-Token": "viewer-1"})
    r.check("a call with a demo token gets the queue", status == 200 and isinstance(
        json.loads(body), list), str(status))
    status, _, _ = get(site + "/api/docs", basic())
    r.check("/api/docs is no page (CREDLENS_ENV=production)", status in (404, 405), str(status))


def check_forwarding(r: Report, echo_site: str) -> None:
    get(echo_site + "/api/merchants?band=Strong", {**basic(), "X-Demo-Token": "officer-2"})
    sent = Echo.seen
    headers = sent.get("headers", {})
    r.check("'/api' is taken off, the query kept", sent.get("path") == "/merchants?band=Strong",
            str(sent.get("path")))
    r.check("the site password is NOT passed to the API", not headers.get("authorization"),
            str(headers.get("authorization")))
    r.check("the demo token IS passed", headers.get("x-demo-token") == "officer-2")
    r.check("the visitor's address is passed", bool(headers.get("x-forwarded-for")))
    r.check("the scheme is passed", headers.get("x-forwarded-proto") == "http")
    big = b"x" * (12 * MEGABYTE)
    post = {**basic(), "Content-Type": "text/csv"}
    status = get(echo_site + "/api/admin/import/merchants", post, big, "POST")[0]
    r.check("a file over 11 MB is stopped by Nginx (413)", status == 413, str(status))


def check_api_down(r: Report, dead_site: str) -> None:
    status, _, body = get(dead_site + "/api/ready", basic())
    r.check("API down: visitors see 'CredLens is starting'",
            status == 502 and b"CredLens is starting" in body, str(status))
    r.check("that page reloads itself", b'http-equiv="refresh"' in body)


def check_flood(r: Report, site: str) -> None:
    codes = {get(site + "/favicon.svg", basic())[0] for _ in range(150)}
    r.check("a flood is answered 429, never 'starting' (503)", 429 in codes and 503 not in codes,
            str(sorted(codes)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Try the Nginx config in Docker.")
    parser.add_argument("--keep-running", action="store_true")
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if docker("info", check=False).returncode != 0:
        print("Docker is not running. Start Docker Desktop, wait for 'Engine running', retry.")
        return 2
    if not (DIST / "index.html").exists():
        print("The dashboard is not built. Run: cd web && npm ci && npm run build")
        return 2

    folder = Path(tempfile.mkdtemp(prefix="credlens-nginx-"))
    htpasswd = folder / "htpasswd"
    digest = base64.b64encode(hashlib.sha1(PASSWORD.encode()).digest()).decode()
    htpasswd.write_text(f"{USER}:{{SHA}}{digest}\n", encoding="utf-8")  # nginx understands {SHA}

    api_up = False
    if port_open(API_PORT):
        api_up = get(f"http://127.0.0.1:{API_PORT}/ready")[0] == 200
    print("API on this laptop:", "running, it is tested too" if api_up else "NOT running (skipped)")

    r = Report()
    confs = {
        SITE: write_config(folder, API_PORT if api_up else 1, "site"),
        ECHO: write_config(folder, ECHO_PORT, "echo"),
        DEAD: write_config(folder, 1, "dead"),
    }
    echo = HTTPServer(("0.0.0.0", ECHO_PORT), Echo)
    threading.Thread(target=echo.serve_forever, daemon=True).start()
    try:
        syntax = docker(
            "run", "--rm", *mounts(confs[SITE], htpasswd), IMAGE, "nginx", "-t", check=False
        )
        r.check("nginx -t accepts the config", syntax.returncode == 0, syntax.stderr.strip()[-400:])
        if syntax.returncode == 0:
            for name, conf in confs.items():
                start(name, conf, htpasswd)
            urls = {name: f"http://127.0.0.1:{port}" for name, port in PORTS.items()}
            for url in urls.values():
                wait_until_up(url + "/")
            check_password(r, urls[SITE])
            check_dashboard(r, urls[SITE])
            if api_up:
                check_api(r, urls[SITE])
            else:
                print("[skip] checks that need the running API")
            check_forwarding(r, urls[ECHO])
            check_api_down(r, urls[DEAD])
            check_flood(r, urls[SITE])
    finally:
        keep = SITE if args.keep_running else None
        docker("rm", "-f", *[n for n in PORTS if n != keep], check=False)
        if keep:
            print(f"\nLeft running: http://localhost:{PORTS[SITE]}")
            print(f"User {USER}, password {PASSWORD}")
            print(f"Stop it with: docker rm -f {SITE}")
        echo.shutdown()
    print("\nAll checks passed." if not r.failed else f"\n{r.failed} check(s) FAILED.")
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
