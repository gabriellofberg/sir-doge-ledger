"""Backup export/restore round-trip tests."""

from app.db import get_db, now_iso
from app.services.data_management import export_backup_json, import_backup_json, wipe_all_data
from app.services.money import tx_hash


def _seed_full_dataset() -> None:
    with get_db() as conn:
        conn.execute(
            "INSERT INTO imports (id, filename, imported_at, row_count, mapping_json) VALUES (1, 'bank.csv', ?, 1, '{}')",
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO transactions (
                id, import_id, tx_date, amount, raw_description, normalized_merchant,
                category, category_source, confidence, needs_review, tx_hash, notes, created_at
            ) VALUES (1, 1, '2026-05-10', -250, 'ZALANDO', 'ZALANDO', 'Shopping', 'auto', 0.9, 0, ?, 'note', ?)
            """,
            (tx_hash("2026-05-10", -250, "ZALANDO"), now_iso()),
        )
        conn.execute(
            "INSERT INTO transaction_tags (transaction_id, tag) VALUES (1, 'clothes')"
        )
        conn.execute(
            """
            INSERT INTO category_rules (id, match_text, category, enabled, created_at)
            VALUES (1, 'ZALANDO', 'Shopping', 1, ?)
            """,
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO recurring_groups (
                id, name, normalized_merchant, cadence, typical_amount, yearly_cost,
                occurrence_count, last_seen, decision, use_it, worth_it, cancel_by, updated_at
            ) VALUES (1, 'Spotify', 'SPOTIFY', 'monthly', 109, 1308, 6, '2026-05-01', 'keep', 'yes', 'yes', NULL, ?)
            """,
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO recurring_price_events
            (id, normalized_merchant, old_amount, new_amount, detected_at, acknowledged)
            VALUES (1, 'SPOTIFY', 99, 109, ?, 0)
            """,
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO life_items (id, title, kind, due_date, amount, notes, created_at, updated_at)
            VALUES (1, 'Hyra', 'rent', '2026-08-01', 8500, NULL, ?, ?)
            """,
            (now_iso(), now_iso()),
        )
        conn.execute(
            "INSERT INTO budgets (category, monthly_limit, enabled, updated_at) VALUES ('Shopping', 2000, 1, ?)",
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO savings_goals (id, name, target_amount, current_amount, updated_at)
            VALUES (1, 'Buffer', 20000, 5000, ?)
            """,
            (now_iso(),),
        )
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES ('monthly_income', '42000', ?)",
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO bank_profiles (id, name, mapping_json, created_at)
            VALUES (1, 'Swedbank', '{"date":"Bokföringsdag"}', ?)
            """,
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO categories (slug, name, is_system, sort_order)
            VALUES ('CustomCat', 'Custom', 0, 99)
            """,
        )


def test_backup_round_trip_restores_everything():
    _seed_full_dataset()
    backup = export_backup_json()
    assert backup["app"] == "sir-doge-ledger"
    assert backup["backup_version"] == 1
    assert len(backup["transactions"]) == 1
    assert len(backup["category_rules"]) == 1
    assert len(backup["app_settings"]) == 1
    assert len(backup["transaction_tags"]) == 1
    assert len(backup["categories"]) >= 1

    wipe_all_data()
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"] == 0

    result = import_backup_json(backup)
    assert result["status"] == "ok"
    assert result["restored"]["transactions"] == 1
    assert result["restored"]["category_rules"] == 1

    with get_db() as conn:
        tx = conn.execute("SELECT * FROM transactions WHERE id = 1").fetchone()
        assert tx["raw_description"] == "ZALANDO"
        assert tx["notes"] == "note"
        tag = conn.execute(
            "SELECT tag FROM transaction_tags WHERE transaction_id = 1"
        ).fetchone()
        assert tag["tag"] == "clothes"
        rule = conn.execute("SELECT category FROM category_rules WHERE id = 1").fetchone()
        assert rule["category"] == "Shopping"
        setting = conn.execute(
            "SELECT value FROM app_settings WHERE key = 'monthly_income'"
        ).fetchone()
        assert setting["value"] == "42000"
        group = conn.execute("SELECT decision FROM recurring_groups WHERE id = 1").fetchone()
        assert group["decision"] == "keep"
        budget = conn.execute(
            "SELECT monthly_limit FROM budgets WHERE category = 'Shopping'"
        ).fetchone()
        assert budget["monthly_limit"] == 2000
        custom = conn.execute("SELECT slug FROM categories WHERE slug = 'CustomCat'").fetchone()
        assert custom is not None


def test_legacy_backup_without_new_tables_imports():
    backup = {
        "app": "sir-doge-ledger",
        "transactions": [],
        "imports": [],
        "category_rules": [],
        "recurring_groups": [],
        "recurring_price_events": [],
        "life_items": [],
        "budgets": [],
        "savings_goals": [],
    }
    result = import_backup_json(backup)
    assert result["status"] == "ok"


def test_import_rejects_invalid_backup():
    try:
        import_backup_json({"app": "other-app"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "SirDoge" in str(exc)


def test_import_backup_api():
    from fastapi.testclient import TestClient

    from app.main import app

    _seed_full_dataset()
    backup = export_backup_json()
    wipe_all_data()

    CSRF = {"X-Sir-Doge": "1"}
    import json

    client = TestClient(app)
    res = client.post(
        "/api/data/import/backup",
        headers=CSRF,
        files={"file": ("backup.json", json.dumps(backup).encode(), "application/json")},
    )
    assert res.status_code == 200
    assert res.json()["restored"]["transactions"] == 1
    assert client.get("/api/money/stats").json()["transaction_count"] == 1
