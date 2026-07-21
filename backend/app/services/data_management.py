"""Export, restore, and wipe user data (keeps password/auth files outside the DB)."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from ..config import UPLOADS_DIR
from ..db import get_db, rows_to_dicts

BACKUP_VERSION = 1

# Every user-data table that a full wipe must clear (auth lives outside SQLite).
_WIPE_TABLES = (
    "categories",
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

_TABLE_COLUMNS: dict[str, list[str]] = {
    "categories": ["slug", "name", "is_system", "sort_order"],
    "imports": ["id", "filename", "imported_at", "row_count", "mapping_json"],
    "bank_profiles": ["id", "name", "mapping_json", "created_at"],
    "category_rules": ["id", "match_text", "category", "enabled", "created_at"],
    "app_settings": ["key", "value", "updated_at"],
    "budgets": ["category", "monthly_limit", "enabled", "updated_at"],
    "savings_goals": ["id", "name", "target_amount", "current_amount", "updated_at"],
    "transactions": [
        "id",
        "import_id",
        "tx_date",
        "amount",
        "raw_description",
        "normalized_merchant",
        "category",
        "category_source",
        "confidence",
        "needs_review",
        "tx_hash",
        "notes",
        "transfer_kind",
        "created_at",
    ],
    "transaction_tags": ["transaction_id", "tag"],
    "recurring_groups": [
        "id",
        "name",
        "normalized_merchant",
        "cadence",
        "typical_amount",
        "yearly_cost",
        "occurrence_count",
        "last_seen",
        "decision",
        "use_it",
        "worth_it",
        "cancel_by",
        "updated_at",
    ],
    "recurring_price_events": [
        "id",
        "normalized_merchant",
        "old_amount",
        "new_amount",
        "detected_at",
        "acknowledged",
    ],
    "life_items": ["id", "title", "kind", "due_date", "amount", "notes", "created_at", "updated_at"],
}

_RESTORE_ORDER: tuple[str, ...] = (
    "categories",
    "imports",
    "bank_profiles",
    "category_rules",
    "app_settings",
    "budgets",
    "savings_goals",
    "transactions",
    "transaction_tags",
    "recurring_groups",
    "recurring_price_events",
    "life_items",
)

_AUTOINCREMENT_TABLES: tuple[str, ...] = (
    "imports",
    "bank_profiles",
    "category_rules",
    "transactions",
    "recurring_groups",
    "recurring_price_events",
    "life_items",
    "savings_goals",
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
        payload: dict[str, Any] = {
            "app": "sir-doge-ledger",
            "backup_version": BACKUP_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        for table in _RESTORE_ORDER:
            payload[table] = rows_to_dicts(
                conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            )
        return payload


def _wipe_db_tables(conn) -> None:
    for table in _WIPE_TABLES:
        conn.execute(f"DELETE FROM {table}")


def _insert_rows(conn, table: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    columns = _TABLE_COLUMNS[table]
    placeholders = ", ".join("?" * len(columns))
    col_sql = ", ".join(columns)
    sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"
    for row in rows:
        conn.execute(sql, [row.get(col) for col in columns])
    return len(rows)


def _fix_sqlite_sequences(conn) -> None:
    for table in _AUTOINCREMENT_TABLES:
        row = conn.execute(f"SELECT MAX(id) AS m FROM {table}").fetchone()
        max_id = row["m"] if row else None
        if max_id is not None:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_sequence WHERE name = ?", (table,)
            ).fetchone()
            if exists:
                conn.execute("UPDATE sqlite_sequence SET seq = ? WHERE name = ?", (max_id, table))
            else:
                conn.execute("INSERT INTO sqlite_sequence (name, seq) VALUES (?, ?)", (table, max_id))
        else:
            conn.execute("DELETE FROM sqlite_sequence WHERE name = ?", (table,))


def _validate_backup(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("backup must be a JSON object")
    if payload.get("app") != "sir-doge-ledger":
        raise ValueError("not a SirDoge Ledger backup file")
    for table in _RESTORE_ORDER:
        rows = payload.get(table, [])
        if rows is None:
            payload[table] = []
        elif not isinstance(rows, list):
            raise ValueError(f"invalid backup: {table} must be a list")
    return payload


def import_backup_json(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace all user data with the contents of a backup file."""
    data = _validate_backup(payload)
    restored: dict[str, int] = {}
    with get_db() as conn:
        _wipe_db_tables(conn)
        conn.execute("DELETE FROM categories")
        for table in _RESTORE_ORDER:
            restored[table] = _insert_rows(conn, table, data.get(table, []))
        _fix_sqlite_sequences(conn)
        if not data.get("categories"):
            from .categories import seed_categories

            seed_categories(conn)
    from .categories import _invalidate_cache

    _invalidate_cache()
    return {"status": "ok", "restored": restored}


def wipe_all_data() -> dict[str, int]:
    """Remove all financial/life/settings data. Auth files outside the DB are kept."""
    with get_db() as conn:
        counts: dict[str, int] = {}
        for table in _WIPE_TABLES:
            counts[table] = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()["c"]
        counts["categories"] = conn.execute("SELECT COUNT(*) AS c FROM categories").fetchone()["c"]
        _wipe_db_tables(conn)
        conn.execute("DELETE FROM categories")

    from .categories import _invalidate_cache, seed_categories

    with get_db() as conn:
        seed_categories(conn)
    _invalidate_cache()

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
