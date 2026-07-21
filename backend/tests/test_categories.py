"""Category CRUD, delete preview, merge, and manual_once protection."""

from app.db import get_db, now_iso
from app.services.categories import (
    create_category,
    delete_category,
    delete_preview,
    merge_categories,
    rename_category,
)
from app.services.money import tx_hash


def _seed_tx(
    conn,
    *,
    tx_date: str,
    amount: float,
    desc: str,
    category: str,
    category_source: str = "auto",
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
            category, category_source, confidence, needs_review, tx_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0.9, 0, ?, ?)
        """,
        (
            iid,
            tx_date,
            amount,
            desc,
            desc.upper(),
            category,
            category_source,
            tx_hash(tx_date, amount, desc),
            now_iso(),
        ),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_create_and_list_category():
    created = create_category("Husdjur")
    assert created["slug"]
    assert created["name"] == "Husdjur"
    assert created["tx_count"] == 0


def test_rename_keeps_slug_and_transactions():
    with get_db() as conn:
        tx_id = _seed_tx(
            conn,
            tx_date="2026-05-10",
            amount=-180.0,
            desc="Kortköp SJ",
            category="Transport",
        )

    renamed = rename_category("Transport", "Resor")
    assert renamed["slug"] == "Transport"
    assert renamed["name"] == "Resor"

    with get_db() as conn:
        tx = conn.execute("SELECT category FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        assert tx["category"] == "Transport"


def test_delete_preview_estimates_outcomes():
    custom = create_category("TestDelete")
    slug = custom["slug"]
    with get_db() as conn:
        _seed_tx(
            conn,
            tx_date="2026-05-10",
            amount=-109.0,
            desc="SPOTIFY AB",
            category=slug,
            category_source="auto",
        )
        _seed_tx(
            conn,
            tx_date="2026-05-11",
            amount=-50.0,
            desc="UNKNOWN SHOP XYZ",
            category=slug,
            category_source="manual_once",
        )
        conn.execute(
            "INSERT INTO category_rules (match_text, category, enabled, created_at) VALUES (?, ?, 1, ?)",
            ("SPOTIFY", slug, now_iso()),
        )
        conn.execute(
            "INSERT INTO budgets (category, monthly_limit, enabled, updated_at) VALUES (?, 500, 1, ?)",
            (slug, now_iso()),
        )

    preview = delete_preview(slug)
    assert preview["tx_count"] == 2
    assert preview["estimated_recategorizable"] == 1
    assert preview["estimated_unclear"] == 1
    assert preview["rules_count"] == 1
    assert preview["budgets_count"] == 1


def test_delete_manual_once_becomes_unclear():
    custom = create_category("ManualOnceCat")
    slug = custom["slug"]
    with get_db() as conn:
        tx_id = _seed_tx(
            conn,
            tx_date="2026-05-10",
            amount=-99.0,
            desc="RANDOM MERCHANT",
            category=slug,
            category_source="manual_once",
        )

    result = delete_category(slug)
    assert result["transactions_unclear"] == 1
    assert result["transactions_recategorized"] == 0

    with get_db() as conn:
        tx = conn.execute("SELECT category, category_source, needs_review FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        assert tx["category"] == "Unclear"
        assert tx["category_source"] == "unclear"
        assert tx["needs_review"] == 1


def test_merge_moves_transactions_rules_and_budget():
    source = create_category("MergeSource")
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO budgets (category, monthly_limit, enabled, updated_at) VALUES ('Shopping', 500, 1, ?)",
            (now_iso(),),
        )
        _seed_tx(
            conn,
            tx_date="2026-05-10",
            amount=-200.0,
            desc="SHOP A",
            category=source["slug"],
        )
        conn.execute(
            "INSERT INTO category_rules (match_text, category, enabled, created_at) VALUES (?, ?, 1, ?)",
            ("SHOP A", source["slug"], now_iso()),
        )
        conn.execute(
            "INSERT INTO budgets (category, monthly_limit, enabled, updated_at) VALUES (?, 1000, 1, ?)",
            (source["slug"], now_iso()),
        )

    result = merge_categories(source["slug"], "Shopping")
    assert result["transactions_moved"] == 1
    assert result["rules_moved"] == 1
    assert result["budget_moved"] == 0

    with get_db() as conn:
        budget = conn.execute(
            "SELECT monthly_limit FROM budgets WHERE category = 'Shopping'"
        ).fetchone()
        assert budget["monthly_limit"] == 500

    with get_db() as conn:
        assert not conn.execute(
            "SELECT 1 FROM categories WHERE slug = ?", (source["slug"],)
        ).fetchone()
        tx = conn.execute("SELECT category FROM transactions WHERE raw_description = 'SHOP A'").fetchone()
        assert tx["category"] == "Shopping"
        rule = conn.execute(
            "SELECT category FROM category_rules WHERE match_text = 'SHOP A'"
        ).fetchone()
        assert rule["category"] == "Shopping"


def test_merge_budget_when_target_has_none():
    source = create_category("BudgetSource")
    with get_db() as conn:
        conn.execute("DELETE FROM budgets WHERE category = 'Groceries'")
        conn.execute(
            "INSERT INTO budgets (category, monthly_limit, enabled, updated_at) VALUES (?, 800, 1, ?)",
            (source["slug"], now_iso()),
        )

    result = merge_categories(source["slug"], "Groceries")
    assert result["budget_moved"] == 1

    with get_db() as conn:
        budget = conn.execute(
            "SELECT monthly_limit FROM budgets WHERE category = 'Groceries'"
        ).fetchone()
        assert budget["monthly_limit"] == 800


def test_cannot_delete_system_category():
    try:
        delete_category("Income")
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "system" in str(exc).lower()


def test_category_api_endpoints():
    from fastapi.testclient import TestClient

    from app.main import app

    CSRF = {"X-Sir-Doge": "1"}
    client = TestClient(app)

    res = client.post("/api/money/categories", headers=CSRF, json={"name": "ApiCat"})
    assert res.status_code == 200
    slug = res.json()["slug"]

    with get_db() as conn:
        _seed_tx(
            conn,
            tx_date="2026-05-10",
            amount=-50.0,
            desc="TEST",
            category=slug,
            category_source="manual_once",
        )

    preview = client.get(f"/api/money/categories/{slug}/delete-preview")
    assert preview.status_code == 200
    body = preview.json()
    assert body["tx_count"] == 1
    assert body["estimated_unclear"] == 1

    merged = client.post(
        f"/api/money/categories/{slug}/merge",
        headers=CSRF,
        json={"target_slug": "Other"},
    )
    assert merged.status_code == 200
    assert merged.json()["transactions_moved"] == 1

    with get_db() as conn:
        assert not conn.execute("SELECT 1 FROM categories WHERE slug = ?", (slug,)).fetchone()
