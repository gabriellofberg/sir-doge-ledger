"""Export and wipe user data (keeps password/auth files outside the DB)."""

from __future__ import annotations

import csv
import io
from typing import Any

from ..config import UPLOADS_DIR
from ..db import get_db, rows_to_dicts

# Every user-data table that a full wipe must clear (auth lives outside SQLite).
_WIPE_TABLES = (
    "transaction_tags",
    "transactions",
    "imports",
    "category_rules",
    "recurring_groups",
    "recurring_price_events",
    "life_items",
    "pending_imports",
    "bank_profiles",
    "budgets",
    "savings_goals",
    "app_settings",
)


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
            "recurring_price_events": rows_to_dicts(
                conn.execute("SELECT * FROM recurring_price_events ORDER BY id").fetchall()
            ),
            "life_items": rows_to_dicts(conn.execute("SELECT * FROM life_items ORDER BY id").fetchall()),
            "budgets": rows_to_dicts(conn.execute("SELECT * FROM budgets ORDER BY category").fetchall()),
            "savings_goals": rows_to_dicts(
                conn.execute("SELECT * FROM savings_goals ORDER BY id").fetchall()
            ),
        }


def wipe_all_data() -> dict[str, int]:
    """Remove all financial/life/settings data. Auth files outside the DB are kept."""
    with get_db() as conn:
        counts: dict[str, int] = {}
        for table in _WIPE_TABLES:
            counts[table] = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        for table in _WIPE_TABLES:
            conn.execute(f"DELETE FROM {table}")

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
