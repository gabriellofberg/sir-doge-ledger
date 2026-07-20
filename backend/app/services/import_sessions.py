"""Opaque import sessions — never expose filesystem paths to the client."""

from __future__ import annotations

import secrets
import uuid
from pathlib import Path
from typing import Any

from ..config import UPLOADS_DIR, ensure_dirs, secure_db_file
from ..db import get_db, now_iso, rows_to_dicts
from .security_paths import safe_upload_name


def create_session(filename: str, path: Path) -> str:
    session_id = secrets.token_urlsafe(24)
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO pending_imports (session_id, filename, path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, filename, str(path.resolve()), now_iso()),
        )
    return session_id


def save_upload(filename: str, data: bytes) -> tuple[str, str]:
    ensure_dirs()
    safe = safe_upload_name(filename)
    dest = UPLOADS_DIR / f"{uuid.uuid4().hex}_{safe}"
    dest.write_bytes(data)
    try:
        import os

        os.chmod(dest, 0o600)
    except OSError:
        pass
    session_id = create_session(safe, dest)
    return session_id, safe


def get_session_path(session_id: str) -> Path:
    with get_db() as conn:
        row = conn.execute(
            "SELECT path, filename FROM pending_imports WHERE session_id = ?",
            (session_id.strip(),),
        ).fetchone()
    if not row:
        raise KeyError("import session not found")
    path = Path(row["path"]).resolve()
    uploads_root = UPLOADS_DIR.resolve()
    if not path.is_relative_to(uploads_root) or not path.is_file():
        raise ValueError("invalid import session path")
    return path


def delete_session(session_id: str, *, remove_file: bool = True) -> None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT path FROM pending_imports WHERE session_id = ?",
            (session_id.strip(),),
        ).fetchone()
        if row and remove_file:
            try:
                Path(row["path"]).unlink(missing_ok=True)
            except OSError:
                pass
        conn.execute("DELETE FROM pending_imports WHERE session_id = ?", (session_id.strip(),))


def purge_old_sessions(max_age_hours: int = 24) -> int:
    """Remove stale pending imports older than max_age_hours."""
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)).replace(microsecond=0)
    cutoff_iso = cutoff.isoformat()
    removed = 0
    with get_db() as conn:
        rows = conn.execute(
            "SELECT session_id, path FROM pending_imports WHERE created_at < ?",
            (cutoff_iso,),
        ).fetchall()
        for row in rows:
            try:
                Path(row["path"]).unlink(missing_ok=True)
            except OSError:
                pass
            conn.execute("DELETE FROM pending_imports WHERE session_id = ?", (row["session_id"],))
            removed += 1
    return removed
