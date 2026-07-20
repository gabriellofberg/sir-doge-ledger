from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from .config import DB_PATH, ensure_dirs, secure_db_file

CATEGORIES = [
    "Housing",
    "Groceries",
    "Transport",
    "Restaurants",
    "Subscriptions",
    "Shopping",
    "Health",
    "Income",
    "Transfers",
    "Fees",
    "Other",
    "Unclear",
]


def _connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
        secure_db_file()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()}
    if "tx_hash" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN tx_hash TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_hash ON transactions(tx_hash) WHERE tx_hash IS NOT NULL"
        )


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                imported_at TEXT NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                mapping_json TEXT
            );

            CREATE TABLE IF NOT EXISTS pending_imports (
                session_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bank_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                mapping_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS category_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_text TEXT NOT NULL,
                category TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(match_text)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                import_id INTEGER REFERENCES imports(id) ON DELETE CASCADE,
                tx_date TEXT NOT NULL,
                amount REAL NOT NULL,
                raw_description TEXT NOT NULL,
                normalized_merchant TEXT NOT NULL,
                category TEXT NOT NULL,
                category_source TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                needs_review INTEGER NOT NULL DEFAULT 0,
                tx_hash TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recurring_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_merchant TEXT NOT NULL,
                cadence TEXT NOT NULL,
                typical_amount REAL NOT NULL,
                yearly_cost REAL NOT NULL,
                occurrence_count INTEGER NOT NULL,
                last_seen TEXT NOT NULL,
                decision TEXT NOT NULL DEFAULT 'pending',
                use_it TEXT,
                worth_it TEXT,
                updated_at TEXT NOT NULL,
                UNIQUE(normalized_merchant, cadence, typical_amount)
            );

            CREATE TABLE IF NOT EXISTS life_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                kind TEXT NOT NULL,
                due_date TEXT,
                amount REAL,
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tx_date ON transactions(tx_date);
            CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category);
            CREATE INDEX IF NOT EXISTS idx_tx_review ON transactions(needs_review);
            CREATE INDEX IF NOT EXISTS idx_tx_merchant ON transactions(normalized_merchant);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_hash ON transactions(tx_hash) WHERE tx_hash IS NOT NULL;
            """
        )
        _migrate(conn)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]
