"""Password sessions — dev open mode optional."""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

from ..config import USER_DATA_DIR, is_dev_open

AUTH_FILE = USER_DATA_DIR / "auth.json"
RECOVERY_HINT_FILE = USER_DATA_DIR / "recovery-hint.txt"
COOKIE_NAME = "sir_doge_session"
DEMO_COOKIE = "sir_doge_demo"
SESSION_DAYS = 30

_sessions: dict[str, dict[str, Any]] = {}


def _read_auth_file() -> dict[str, Any]:
    try:
        return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_auth_file(data: dict[str, Any]) -> None:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(AUTH_FILE, 0o600)
    except OSError:
        pass


def needs_setup() -> bool:
    if is_dev_open():
        return False
    return not _read_auth_file().get("password_hash")


def auth_enabled() -> bool:
    if is_dev_open():
        return False
    return bool(_read_auth_file().get("password_hash"))


def auth_status() -> dict[str, Any]:
    data = _read_auth_file()
    return {
        "needs_setup": needs_setup(),
        "auth_required": auth_enabled(),
        "dev_open": is_dev_open(),
        "encryption_enabled": bool(data.get("encryption_enabled")),
        "has_recovery_hint": RECOVERY_HINT_FILE.is_file(),
    }


def setup_password(password: str, *, enable_encryption: bool = False) -> dict[str, str]:
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    recovery_key = secrets.token_urlsafe(16)
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    recovery_hash = bcrypt.hashpw(recovery_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    _write_auth_file(
        {
            "password_hash": password_hash,
            "recovery_hash": recovery_hash,
            "encryption_enabled": enable_encryption,
        }
    )
    RECOVERY_HINT_FILE.write_text(
        "SirDoge recovery key — store safely. Needed if you forget your password.\n\n"
        f"{recovery_key}\n\n"
        "In dev you can also delete auth.json to reset.\n",
        encoding="utf-8",
    )
    try:
        os.chmod(RECOVERY_HINT_FILE, 0o600)
    except OSError:
        pass
    session = _create_session(is_demo=False)
    return {"recovery_key": recovery_key, "session": session}


def verify_password(password: str) -> bool:
    data = _read_auth_file()
    stored = data.get("password_hash")
    if not stored:
        return False
    return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))


def recover_password(recovery_key: str, new_password: str) -> bool:
    data = _read_auth_file()
    stored = data.get("recovery_hash")
    if not stored or len(new_password) < 8:
        return False
    if not bcrypt.checkpw(recovery_key.encode("utf-8"), stored.encode("utf-8")):
        return False
    data["password_hash"] = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    _write_auth_file(data)
    return True


def _create_session(*, is_demo: bool) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    _sessions[token] = {"is_demo": is_demo, "expires": expires.isoformat()}
    return token


def create_login_session() -> str:
    return _create_session(is_demo=False)


def create_demo_session() -> str:
    return _create_session(is_demo=True)


def _session_valid(token: str | None) -> bool:
    if not token:
        return False
    entry = _sessions.get(token.strip())
    if not entry:
        return False
    expires = datetime.fromisoformat(entry["expires"])
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        _sessions.pop(token.strip(), None)
        return False
    return True


def session_matches(token: str | None) -> bool:
    if is_dev_open():
        return True
    if not auth_enabled():
        return True
    return _session_valid(token)


def is_demo_session(token: str | None) -> bool:
    if not token:
        return False
    entry = _sessions.get(token.strip())
    return bool(entry and entry.get("is_demo"))


def invalidate_session(token: str | None) -> None:
    if token:
        _sessions.pop(token.strip(), None)


# Legacy token helpers (removed from UX; kept for migration tests)
TOKEN_FILE = USER_DATA_DIR / "api-token"
COOKIE_NAME_LEGACY = "sir_doge_token"


def token_hint(_token: str | None = None) -> str:
    return "****"
