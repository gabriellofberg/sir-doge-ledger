"""Local API token — always required when started via run.sh / launcher."""

from __future__ import annotations

import os
import secrets

from ..config import USER_DATA_DIR

TOKEN_FILE = USER_DATA_DIR / "api-token"
COOKIE_NAME = "sir_doge_token"


def _read_token_file() -> str:
    try:
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def get_token() -> str:
    env = os.environ.get("SIR_DOGE_TOKEN")
    if env:
        return env.strip()
    return _read_token_file()


def ensure_token() -> str:
    existing = get_token()
    if existing:
        return existing
    token = secrets.token_urlsafe(32)
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    try:
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass
    os.environ["SIR_DOGE_TOKEN"] = token
    return token


def auth_enabled() -> bool:
    return bool(get_token())


def token_matches(candidate: str | None) -> bool:
    token = get_token()
    if not token or not candidate:
        return False
    return secrets.compare_digest(token, candidate.strip())
