"""Filesystem safety helpers."""

from __future__ import annotations

from pathlib import Path

from ..config import UPLOADS_DIR


def resolve_upload_path(raw: str) -> Path:
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
