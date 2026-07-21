"""Seed and manage the isolated demo database."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..config import SAMPLE_DATA_DIR, demo_db_path, ensure_dirs
from ..db import init_db_file, now_iso
from .categorize import categorize
from .import_parse import ColumnMapping, parse_all_rows
from .import_sessions import save_upload
from .normalize import normalize_merchant


def ensure_demo_db() -> None:
    path = demo_db_path()
    if path.exists():
        return
    ensure_dirs()
    init_db_file(str(path))
    import sqlite3

    from .categories import seed_categories

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        seed_categories(conn)
        conn.commit()
    finally:
        conn.close()
    _seed_demo(path)


def _tx_hash(tx_date: str, amount: float, description: str) -> str:
    payload = f"{tx_date}|{amount:.2f}|{description.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _seed_demo(path: Path) -> None:
    import sqlite3

    sample = SAMPLE_DATA_DIR / "sample_transactions.csv"
    if not sample.is_file():
        return
    sid, _ = save_upload("demo_sample.csv", sample.read_bytes())
    from .import_sessions import get_session_path

    mapping = ColumnMapping(
        date="Bokföringsdag",
        amount="Belopp",
        description="Text",
        amount_decimal=",",
        delimiter=";",
    )
    rows = parse_all_rows(get_session_path(sid), mapping)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    now = now_iso()
    conn.execute(
        "INSERT INTO imports (filename, imported_at, row_count) VALUES (?, ?, ?)",
        ("demo_sample.csv", now, len(rows)),
    )
    import_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    for r in rows:
        conn.execute(
            """
            INSERT INTO transactions (
                import_id, tx_date, amount, raw_description, normalized_merchant,
                category, category_source, confidence, needs_review, tx_hash, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                import_id,
                r.tx_date,
                r.amount,
                r.description,
                normalize_merchant(r.description),
                categorize(r.description, r.amount, []).category,
                "auto",
                0.85,
                0,
                _tx_hash(r.tx_date, r.amount, r.description),
                now,
            ),
        )
    conn.execute(
        """
        INSERT INTO app_settings (key, value, updated_at) VALUES ('monthly_income', ?, ?)
        """,
        (json.dumps(42000), now),
    )
    conn.commit()
    conn.close()
    from .import_sessions import delete_session

    delete_session(sid, remove_file=True)


def reset_demo_db() -> None:
    path = demo_db_path()
    if path.exists():
        path.unlink()
    ensure_demo_db()
