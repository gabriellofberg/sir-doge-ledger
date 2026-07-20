"""App settings stored in SQLite."""

from __future__ import annotations

import json
from typing import Any

from ..db import get_db, now_iso

DEFAULTS: dict[str, Any] = {
    "language": "sv",
    "theme": "light",
    "default_months": 12,
    "delete_upload_after_import": True,
    "default_date_format": "auto",
    "monthly_income": 0,
    "encryption_enabled": False,
    "default_bank_profile": "",
}


def get_setting(key: str, default: Any = None) -> Any:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return DEFAULTS.get(key, default)
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def get_all_settings() -> dict[str, Any]:
    out = dict(DEFAULTS)
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    for row in rows:
        try:
            out[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            out[row["key"]] = row["value"]
    return out


def set_setting(key: str, value: Any) -> None:
    payload = json.dumps(value)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (key, payload, now_iso()),
        )


def set_many(values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if key in DEFAULTS or key.startswith("category_"):
            set_setting(key, value)
    return get_all_settings()
