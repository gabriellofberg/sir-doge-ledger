import pytest
from pathlib import Path

from app.services.import_parse import ColumnMapping
from app.services.money import cashflow, commit_import_session, tx_hash
from app.services.security_paths import resolve_upload_path
from app.services.import_sessions import save_upload


def test_tx_hash_stable():
    h1 = tx_hash("2026-01-05", -109.0, "SPOTIFY AB")
    h2 = tx_hash("2026-01-05", -109.0, "SPOTIFY AB")
    assert h1 == h2


def test_dedup_skips_second_import():
    csv = Path(__file__).resolve().parents[2] / "sample_data" / "sample_transactions.csv"
    data = csv.read_bytes()
    sid1, _ = save_upload("sample.csv", data)
    mapping = ColumnMapping(
        date="Bokföringsdag",
        amount="Belopp",
        description="Text",
        amount_decimal=",",
        delimiter=";",
    )
    r1 = commit_import_session(sid1, mapping, "sample.csv")
    assert r1["row_count"] > 0
    sid2, _ = save_upload("sample.csv", data)
    r2 = commit_import_session(sid2, mapping, "sample.csv")
    assert r2["skipped_count"] == r1["row_count"]
    assert r2["row_count"] == 0


def test_cashflow_excludes_transfers():
    from app.db import get_db, now_iso

    with get_db() as conn:
        conn.execute(
            "INSERT INTO imports (filename, imported_at, row_count) VALUES ('t', ?, 0)",
            (now_iso(),),
        )
        iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """
            INSERT INTO transactions (
                import_id, tx_date, amount, raw_description, normalized_merchant,
                category, category_source, confidence, needs_review, tx_hash, created_at
            ) VALUES (?, '2026-06-01', 1000, 'LON', 'LON', 'Income', 'auto', 0.9, 0, ?, ?)
            """,
            (iid, tx_hash("2026-06-01", 1000, "LON"), now_iso()),
        )
        conn.execute(
            """
            INSERT INTO transactions (
                import_id, tx_date, amount, raw_description, normalized_merchant,
                category, category_source, confidence, needs_review, tx_hash,
                transfer_kind, created_at
            ) VALUES (?, '2026-06-02', 500, 'TRANSFER', 'TRANSFER', 'Transfers', 'auto', 0.9, 0, ?, 'internal', ?)
            """,
            (iid, tx_hash("2026-06-02", 500, "TRANSFER"), now_iso()),
        )
    rows = cashflow(12)
    assert rows
    assert rows[-1]["income"] == 1000
    assert rows[-1]["transfer_volume"] == 500


def test_resolve_upload_rejects_traversal(tmp_path):
    evil = tmp_path / "evil.csv"
    evil.write_text("x")
    with pytest.raises(ValueError, match="outside"):
        resolve_upload_path(str(evil))


def test_auth_required(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    import app.services.auth as auth_mod

    monkeypatch.setattr(auth_mod, "auth_enabled", lambda: True)
    monkeypatch.setattr(auth_mod, "session_matches", lambda _t: False)
    c = TestClient(app)
    r = c.get("/api/money/stats")
    assert r.status_code == 401


def test_auth_with_dev_open():
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/money/stats")
    assert r.status_code == 200
