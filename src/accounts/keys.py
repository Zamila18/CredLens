"""The server's secret key, used to hash invitation codes (HMAC) so that a copy of the database
alone cannot be used to test guesses.

`CREDLENS_SECRET_KEY` in the private .env (at least 32 characters). On a production server it
is required. In development, when it is not set, a random key is made once and kept in
`data/.secret_key` (ignored by git), so codes keep working across restarts.
"""

from __future__ import annotations

import os
import secrets

from dotenv import load_dotenv

from src.config import PROJECT_ROOT

MIN_CHARS = 32
KEY_FILE = PROJECT_ROOT / "data" / ".secret_key"


def secret_key() -> str:
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.environ.get("CREDLENS_SECRET_KEY", "").strip()
    if key:
        if len(key) < MIN_CHARS:
            raise RuntimeError(f"CREDLENS_SECRET_KEY must have at least {MIN_CHARS} characters.")
        return key
    if os.environ.get("CREDLENS_ENV", "").strip().lower() == "production":
        raise RuntimeError("Set CREDLENS_SECRET_KEY in the server's environment (.env).")
    if KEY_FILE.is_file():
        return KEY_FILE.read_text(encoding="utf-8").strip()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_hex(32)
    KEY_FILE.write_text(key, encoding="utf-8")
    return key
