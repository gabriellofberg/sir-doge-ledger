"""Filesystem safety helpers."""

from __future__ import annotations

from pathlib import Path


def resolve_upload_path(raw: str) -> Path:
    from ..config import UPLOADS_DIR

    if not raw or not raw.strip():
        raise ValueError("empty path")
    candidate = Path(raw).expanduser().resolve()
    uploads_root = UPLOADS_DIR.resolve()
    if not candidate.is_relative_to(uploads_root):
        raise ValueError("path outside uploads directory")
    if not candidate.is_file():
        raise ValueError("upload file not found")
    return candidate


def safe_upload_name(filename: str) -> str:
    name = Path(filename or "upload.csv").name
    if name in {"", ".", ".."}:
        return "upload.csv"
    return name


def escape_like_pattern(text: str) -> str:
    """Escape SQL LIKE metacharacters (% and _)."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def safe_unlink_upload(raw_path: str) -> None:
    """Delete an upload only if it resolves inside UPLOADS_DIR."""
    try:
        resolve_upload_path(raw_path).unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
