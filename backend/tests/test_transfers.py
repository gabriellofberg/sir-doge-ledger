"""Transfer classification and summary."""

from app.db import get_db, now_iso
from app.services.categorize import categorize
from app.services.money import (
    cashflow,
    classify_transfer,
    completeness,
    transfer_summary,
    tx_hash,
)


def _seed_tx(
    conn,
    *,
    tx_date: str,
    amount: float,
    desc: str,
    category: str = "Transfers",
    transfer_kind: str | None = "internal",
) -> int:
    conn.execute(
        "INSERT INTO imports (filename, imported_at, row_count) VALUES ('t', ?, 1)",
        (now_iso(),),
    )
    iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        """
        INSERT INTO transactions (
            import_id, tx_date, amount, raw_description, normalized_merchant,
            category, category_source, confidence, needs_review, tx_hash,
            transfer_kind, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'auto', 0.9, 0, ?, ?, ?)
        """,
        (
            iid,
            tx_date,
            amount,
            desc,
            desc.upper(),
            category,
            tx_hash(tx_date, amount, desc),
            transfer_kind,
            now_iso(),
        ),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_auto_internal_transfer_gets_transfer_kind():
    r = categorize("Överföring 3058 22 82136", 15000.0, [])
    assert r.category == "Transfers"
    assert r.transfer_kind == "internal"


def test_transfer_summary_breakdown():
    with get_db() as conn:
        _seed_tx(conn, tx_date="2026-07-01", amount=-10.0, desc="XTRASPAR", transfer_kind="internal")
        _seed_tx(conn, tx_date="2026-07-02", amount=5000.0, desc="UNKNOWN MOVE", transfer_kind=None)

    summary = transfer_summary()
    assert summary["internal_count"] == 1
    assert summary["internal_volume"] == 10.0
    assert summary["pending_count"] == 1
    assert summary["pending_volume"] == 5000.0


def test_classify_transfer_expense_counts_in_spent():
    with get_db() as conn:
        tx_id = _seed_tx(
            conn,
            tx_date="2026-07-16",
            amount=-6500.0,
            desc="SWISH BETALNING ERIK",
            transfer_kind=None,
        )

    classify_transfer([tx_id], "expense", category="Other")

    with get_db() as conn:
        row = conn.execute("SELECT category, transfer_kind FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    assert row["category"] == "Other"
    assert row["transfer_kind"] is None

    rows = cashflow(12)
    assert any(float(r["spent"]) < 0 for r in rows)


def test_classify_transfer_income_counts_in_income():
    with get_db() as conn:
        tx_id = _seed_tx(
            conn,
            tx_date="2026-07-16",
            amount=15000.0,
            desc="ÖVERFÖRING SPAR",
            transfer_kind=None,
        )

    classify_transfer([tx_id], "income")

    with get_db() as conn:
        row = conn.execute("SELECT category FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    assert row["category"] == "Income"


def test_completeness_includes_transfer_summary():
    with get_db() as conn:
        _seed_tx(conn, tx_date="2026-07-01", amount=-100.0, desc="XTRASPAR")

    data = completeness()
    assert "transfer_summary" in data
    assert data["transfer_summary"]["internal_count"] >= 1
