"""Password and token hashing.

Passwords: Argon2id (argon2-cffi), stored as the library's own "$argon2id$v=19$m=...$..."
string, which carries its salt and cost so the cost can be raised later. Hashes made before
Argon2 was adopted ("scrypt$n$r$p$salt$hash", stdlib scrypt) still verify; `needs_rehash`
tells the caller to store a fresh Argon2id hash after a successful sign-in.

Password policy (`password_problems`): at least `min_chars` characters, upper and lower case,
a digit and a symbol, not a very common password (the list in common_passwords.txt), and not
built from the person's own email or name. The list shipped here is short; a larger public
list can be dropped into the same file, one password per line, without any code change.

Tokens (session tokens, setup codes) are long random values; only their SHA-256 is stored.
Invitation codes are stored as a keyed hash (`keyed_code_hash`), see src/accounts/invitations.py.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from functools import lru_cache
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

# Argon2id parameters: 64 MiB, 3 passes, 1 lane (the library's recommended low-memory profile).
_HASHER = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=1)

# The older scrypt format, kept so existing hashes still verify.
N, R, P = 2**14, 8, 1
KEY_BYTES = 32
MAX_MEM = 64 * 1024 * 1024

COMMON_PASSWORDS_FILE = Path(__file__).with_name("common_passwords.txt")
MAX_PASSWORD_CHARS = 200


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def _verify_scrypt(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.b64decode(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
            maxmem=MAX_MEM,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def verify_password(password: str, stored: str | None) -> bool:
    """True when `password` matches the stored hash. Never raises on a bad stored value."""
    stored = stored or ""
    if stored.startswith("$argon2"):
        try:
            return _HASHER.verify(stored, password)
        except (VerificationError, InvalidHashError):
            return False
    return _verify_scrypt(password, stored)


def needs_rehash(stored: str | None) -> bool:
    """True for a scrypt hash or an Argon2id hash made with older parameters."""
    stored = stored or ""
    if not stored.startswith("$argon2"):
        return True
    try:
        return _HASHER.check_needs_rehash(stored)
    except InvalidHashError:
        return True


@lru_cache(maxsize=1)
def _common_passwords() -> frozenset[str]:
    try:
        lines = COMMON_PASSWORDS_FILE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return frozenset()
    return frozenset(line.strip().lower() for line in lines if line.strip())


def _alnum(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def password_problems(
    password: str,
    *,
    min_chars: int = 12,
    email: str | None = None,
    names: tuple[str, ...] = (),
) -> list[str]:
    """What is wrong with a password, as short sentences (empty when it is acceptable)."""
    problems: list[str] = []
    password = password or ""
    if len(password) < min_chars:
        problems.append(f"Use at least {min_chars} characters.")
    if len(password) > MAX_PASSWORD_CHARS:
        problems.append(f"Use at most {MAX_PASSWORD_CHARS} characters.")
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password):
        problems.append("Use both upper-case and lower-case letters.")
    if not re.search(r"\d", password):
        problems.append("Include at least one digit.")
    if not re.search(r"[^A-Za-z0-9]", password):
        problems.append("Include at least one symbol, for example ! or #.")
    flat = _alnum(password)
    if password.lower() in _common_passwords() or flat in _common_passwords():
        problems.append("This is a very common password. Choose something less guessable.")
    parts = [_alnum((email or "").split("@")[0])] + [_alnum(n) for n in names]
    if any(len(part) >= 4 and part in flat for part in parts):
        problems.append("Do not build the password from your email address or name.")
    return problems


def new_token() -> str:
    """A session token: 256 random bits, URL-safe."""
    return secrets.token_urlsafe(32)


CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no look-alike letters


def new_setup_code() -> str:
    """A one-time setup code an administrator can read out or send: 12 characters, no
    look-alike letters, grouped as XXXX-XXXX-XXXX."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def new_invitation_code() -> str:
    """A company invitation code: 16 characters (about 80 bits), grouped XXXX-XXXX-XXXX-XXXX."""
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(16))
    return "-".join(raw[i : i + 4] for i in range(0, 16, 4))


def session_hash(token: str) -> str:
    """What is stored for a session token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def clean_code(code: str) -> str:
    """Case, spaces and dashes typed by a person are ignored."""
    return "".join(ch for ch in (code or "").upper() if ch.isalnum())


def code_hash(code: str) -> str:
    """What is stored for a setup code (SHA-256 of the cleaned code)."""
    return hashlib.sha256(clean_code(code).encode("utf-8")).hexdigest()


def keyed_code_hash(code: str, secret: str) -> str:
    """What is stored for an invitation code: HMAC-SHA256 with the server's secret key, so a
    copy of the database alone cannot be used to test guesses."""
    return hmac.new(secret.encode("utf-8"), clean_code(code).encode("utf-8"), "sha256").hexdigest()
