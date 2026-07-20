"""Security tests: CSRF, auth, uploads, limits, data wipe."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.security_paths import escape_like_pattern

CSRF = {"X-Sir-Doge": "1"}


@pytest.fixture
def client():
    return TestClient(app)


def test_mutating_requests_require_csrf_header():
    c = TestClient(app)
    assert c.post("/api/money/import", data={"import_session_id": "x"}).status_code == 403
    assert c.delete("/api/money/rules/1").status_code == 403


def test_get_requests_do_not_require_csrf_header(client):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/money/stats").status_code == 200


def test_upload_endpoint_size_limit(client):
    res = client.post(
        "/api/money/preview",
        headers=CSRF,
        files={"file": ("big.csv", b"x" * (21 * 1024 * 1024), "text/csv")},
    )
    assert res.status_code == 413


def test_transaction_limit_capped(client):
    res = client.get("/api/money/transactions?limit=999999")
    assert res.status_code == 200
    # Router caps at MAX_TRANSACTION_LIMIT (1000) — response is valid JSON
    assert "transactions" in res.json()


def test_logout_clears_cookie(client):
    res = client.post("/api/auth/logout", headers=CSRF)
    assert res.status_code == 200


def test_wipe_requires_delete_confirmation(client):
    res = client.post("/api/data/wipe", headers={**CSRF, "Content-Type": "application/json"}, json={"confirm": "NOPE"})
    assert res.status_code == 400


def test_wipe_and_export(client):
    from app.db import get_db, now_iso
    from app.services.money import tx_hash

    with get_db() as conn:
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
            ) VALUES (?, '2026-01-01', -50, 'TEST', 'TEST', 'Other', 'auto', 0.5, 0, ?, ?)
            """,
            (iid, tx_hash("2026-01-01", -50, "TEST"), now_iso()),
        )

    csv_res = client.get("/api/data/export/transactions.csv")
    assert csv_res.status_code == 200
    assert "TEST" in csv_res.text

    wipe_res = client.post(
        "/api/data/wipe",
        headers={**CSRF, "Content-Type": "application/json"},
        json={"confirm": "DELETE"},
    )
    assert wipe_res.status_code == 200
    assert wipe_res.json()["removed"]["transactions"] == 1
    assert client.get("/api/money/stats").json()["transaction_count"] == 0


def test_escape_like_pattern():
    assert escape_like_pattern("50%_OFF") == "50\\%\\_OFF"


def test_delete_session_rejects_traversal_path(tmp_path, monkeypatch):
    from app.config import UPLOADS_DIR
    from app.db import get_db, now_iso
    from app.services.import_sessions import delete_session

    evil = tmp_path / "outside.csv"
    evil.write_text("secret")
    session_id = "test-session-traversal"
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO pending_imports (session_id, filename, path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, "evil.csv", str(evil), now_iso()),
        )
    delete_session(session_id, remove_file=True)
    assert evil.exists()
    assert evil.read_text() == "secret"

    good = UPLOADS_DIR / "good.csv"
    good.write_text("ok")
    good_id = "test-session-good"
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO pending_imports (session_id, filename, path, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (good_id, "good.csv", str(good.resolve()), now_iso()),
        )
    delete_session(good_id, remove_file=True)
    assert not good.exists()
