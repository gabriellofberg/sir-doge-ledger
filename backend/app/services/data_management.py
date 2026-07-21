"""Export and wipe user data (keeps API token)."""

from __future__ import annotations

import csv
import io
from typing import Any

from ..config import UPLOADS_DIR
from ..db import get_db, rows_to_dicts


def export_transactions_csv() -> str:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT tx_date, amount, raw_description, normalized_merchant,
                   category, category_source, confidence, needs_review
            FROM transactions
            ORDER BY tx_date DESC, id DESC
            """
        ).fetchall()
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        [
            "tx_date",
            "amount",
            "raw_description",
            "normalized_merchant",
            "category",
            "category_source",
            "confidence",
            "needs_review",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row["tx_date"],
                row["amount"],
                row["raw_description"],
                row["normalized_merchant"],
                row["category"],
                row["category_source"],
                row["confidence"],
                row["needs_review"],
            ]
        )
    return buf.getvalue()


def export_backup_json() -> dict[str, Any]:
    with get_db() as conn:
        return {
            "app": "sir-doge-ledger",
            "transactions": rows_to_dicts(conn.execute("SELECT * FROM transactions ORDER BY id").fetchall()),
            "imports": rows_to_dicts(conn.execute("SELECT * FROM imports ORDER BY id").fetchall()),
            "category_rules": rows_to_dicts(
                conn.execute("SELECT * FROM category_rules ORDER BY id").fetchall()
            ),
            "recurring_groups": rows_to_dicts(
                conn.execute("SELECT * FROM recurring_groups ORDER BY id").fetchall()
            ),
            "life_items": rows_to_dicts(conn.execute("SELECT * FROM life_items ORDER BY id").fetchall()),
        }


def wipe_all_data() -> dict[str, int]:
    """Remove all financial/life data. API token is kept."""
    with get_db() as conn:
        counts = {
            "transactions": conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"],
            "imports": conn.execute("SELECT COUNT(*) AS c FROM imports").fetchone()["c"],
            "category_rules": conn.execute("SELECT COUNT(*) AS c FROM category_rules").fetchone()["c"],
            "recurring_groups": conn.execute("SELECT COUNT(*) AS c FROM recurring_groups").fetchone()["c"],
            "life_items": conn.execute("SELECT COUNT(*) AS c FROM life_items").fetchone()["c"],
            "pending_imports": conn.execute("SELECT COUNT(*) AS c FROM pending_imports").fetchone()["c"],
        }
        conn.execute("DELETE FROM transactions")
        conn.execute("DELETE FROM imports")
        conn.execute("DELETE FROM category_rules")
        conn.execute("DELETE FROM recurring_groups")
        conn.execute("DELETE FROM life_items")
        conn.execute("DELETE FROM pending_imports")
        conn.execute("DELETE FROM bank_profiles")

    removed_uploads = 0
    if UPLOADS_DIR.is_dir():
        for item in UPLOADS_DIR.iterdir():
            if item.is_file():
                try:
                    item.unlink()
                    removed_uploads += 1
                except OSError:
                    pass

    return {**counts, "upload_files": removed_uploads}
