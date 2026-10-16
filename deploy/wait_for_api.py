"""Wait until the API can answer, then say so. Standard library only.

Purpose: the API needs about 30 seconds to start (it builds the scorer first, and its port does
    not answer until it has). Run this after starting or restarting the service, and before
    opening the site, so nobody sees a "bad gateway" page.
Owner role: D (full-stack).
Implements: Phase 12 (health check that waits for the scorer).

    python deploy/wait_for_api.py                              this machine, port 8000
    python deploy/wait_for_api.py --url http://127.0.0.1:8000 --timeout 180

Exit code 0: the API is ready. Exit code 1: it did not become ready in time, or it started
but says it cannot score (the reason is printed).

It asks GET /ready, which needs no token and says nothing private.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 180
DEFAULT_INTERVAL_SECONDS = 3
REQUEST_TIMEOUT_SECONDS = 5


def ask_ready(base_url: str) -> tuple[str, dict]:
    """One question to /ready. Returns ("ready" | "not_ready" | "not_answering", body)."""
    try:
        with urllib.request.urlopen(
            base_url.rstrip("/") + "/ready", timeout=REQUEST_TIMEOUT_SECONDS
        ) as response:
            return "ready", json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            body = json.loads(error.read().decode("utf-8"))
        except ValueError:
            body = {}
        return ("not_ready" if error.code == 503 else "not_answering"), body
    except (urllib.error.URLError, OSError, ValueError):
        return "not_answering", {}


def wait_for_api(
    base_url: str = DEFAULT_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    interval: float = DEFAULT_INTERVAL_SECONDS,
    ask: Callable[[str], tuple[str, dict]] = ask_ready,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    say: Callable[[str], None] = print,
) -> bool:
    """Ask until the API is ready (True) or the time is up (False)."""
    started = clock()
    last_problems: list[str] = []
    while True:
        state, body = ask(base_url)
        waited = int(clock() - started)
        if state == "ready":
            version = body.get("model_version") or "unknown"
            say(f"READY after {waited} s. Model version: {version}")
            return True
        if state == "not_ready":
            problems = list(body.get("problems") or ["the API says it is not ready"])
            if problems != last_problems:
                say(f"[{waited:>3} s] answering, but not ready: " + " | ".join(problems))
                last_problems = problems
        else:
            say(f"[{waited:>3} s] not answering yet (it takes 30 to 60 seconds to start) ...")
        if clock() - started + interval > timeout:
            say(
                f"NOT READY after {waited} s. Look at the log: "
                "journalctl -u credlens-api -n 80 --no-pager  "
                "and run: python -m src.api.preflight --server"
            )
            return False
        sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wait until the CredLens API is ready.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"default {DEFAULT_URL}")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS)
    args = parser.parse_args(argv)
    ready = wait_for_api(args.url, args.timeout, args.interval)
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
