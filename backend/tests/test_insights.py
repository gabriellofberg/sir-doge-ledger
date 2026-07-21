"""Insight generation and filtered price alerts."""

from datetime import date, timedelta

from app.db import get_db, now_iso
from app.services.insights import generate_insights
from app.services.money import price_alerts, tx_hash
from app.services.settings import set_setting


def _seed_tx(
    conn,
    *,
    tx_date: str,
    amount: float,
    desc: str,
    category: str,
    merchant: str | None = None,
) -> int:
    conn.execute(
        "INSERT INTO imports (filename, imported_at, row_count) VALUES ('t', ?, 1)",
        (now_iso(),),
    )
    iid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    m = merchant or desc.upper()
    conn.execute(
        """
        INSERT INTO transactions (
            import_id, tx_date, amount, raw_description, normalized_merchant,
            category, category_source, confidence, needs_review, tx_hash, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'auto', 0.9, 0, ?, ?)
        """,
        (iid, tx_date, amount, desc, m, category, tx_hash(tx_date, amount, desc), now_iso()),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _seed_recurring_group(conn, *, merchant: str, name: str = "Spotify") -> int:
    conn.execute(
        """
        INSERT INTO recurring_groups (
            name, normalized_merchant, cadence, typical_amount, yearly_cost,
            occurrence_count, last_seen, decision, use_it, worth_it, cancel_by, updated_at
        ) VALUES (?, ?, 'monthly', 109, 1308, 6, '2026-06-05', 'pending', NULL, NULL, NULL, ?)
        """,
        (name, merchant, now_iso()),
    )
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_savings_scenario_for_top_category():
    today = date.today()
    for i in range(6):
        d = (today - timedelta(days=30 * i)).isoformat()
        with get_db() as conn:
            _seed_tx(
                conn,
                tx_date=d,
                amount=-600.0,
                desc="FOODORA",
                category="Restaurants",
                merchant="FOODORA",
            )

    insights = generate_insights(12)
    kinds = [i["kind"] for i in insights]
    assert "savings_scenario" in kinds
    savings = next(i for i in insights if i["kind"] == "savings_scenario")
    assert savings["params"]["category"] == "Restaurants"
    assert savings["params"]["savings"] >= 100


def test_top_merchant_insight():
    today = date.today()
    with get_db() as conn:
        for i in range(4):
            d = (today - timedelta(days=20 * i)).isoformat()
            _seed_tx(
                conn,
                tx_date=d,
                amount=-800.0,
                desc="ICA MAXI",
                category="Groceries",
                merchant="ICA MAXI",
            )
        for i in range(2):
            d = (today - timedelta(days=15 * i)).isoformat()
            _seed_tx(
                conn,
                tx_date=d,
                amount=-200.0,
                desc="BREWDOG",
                category="Restaurants",
                merchant="BREWDOG",
            )

    insights = generate_insights(12)
    top = next((i for i in insights if i["kind"] == "top_merchant"), None)
    assert top is not None
    assert top["params"]["merchant"] == "ICA MAXI"


def test_insights_capped_at_five():
    today = date.today()
    with get_db() as conn:
        for i in range(8):
            d = (today - timedelta(days=25 * i)).isoformat()
            _seed_tx(
                conn,
                tx_date=d,
                amount=-500.0 - i,
                desc=f"SHOP{i}",
                category="Shopping",
                merchant=f"SHOP{i}",
            )

    insights = generate_insights(12)
    assert len(insights) <= 5


def test_price_alerts_only_for_recurring_groups():
    with get_db() as conn:
        _seed_recurring_group(conn, merchant="SPOTIFY", name="Spotify")
        for i in range(3):
            _seed_tx(
                conn,
                tx_date=f"2026-0{i + 1:02d}-05",
                amount=-99.0,
                desc=f"SPOTIFY AB old {i}",
                category="Subscriptions",
                merchant="SPOTIFY",
            )
        for i in range(3):
            _seed_tx(
                conn,
                tx_date=f"2026-0{i + 4:02d}-05",
                amount=-129.0,
                desc=f"SPOTIFY AB new {i}",
                category="Subscriptions",
                merchant="SPOTIFY",
            )
        _seed_tx(
            conn,
            tx_date="2026-03-05",
            amount=-150.0,
            desc="BREWDOG",
            category="Restaurants",
            merchant="BREWDOG",
        )
        _seed_tx(
            conn,
            tx_date="2026-04-05",
            amount=-250.0,
            desc="BREWDOG",
            category="Restaurants",
            merchant="BREWDOG",
        )
        _seed_tx(
            conn,
            tx_date="2026-05-05",
            amount=-300.0,
            desc="BREWDOG",
            category="Restaurants",
            merchant="BREWDOG",
        )

    alerts = price_alerts()
    merchants = {a["normalized_merchant"] for a in alerts}
    assert "SPOTIFY" in merchants or any("SPOTIFY" in m for m in merchants)
    assert "BREWDOG" not in merchants
    if alerts:
        first = alerts[0]
        assert "name" in first
        assert "cadence" in first
        assert "yearly_delta" in first
        assert "recurring_group_id" in first


def test_income_share_when_over_guideline():
    set_setting("monthly_income", "10000")
    today = date.today()
    with get_db() as conn:
        for i in range(6):
            d = (today - timedelta(days=20 * i)).isoformat()
            _seed_tx(
                conn,
                tx_date=d,
                amount=-2000.0,
                desc="RESTAURANT",
                category="Restaurants",
                merchant="RESTAURANT",
            )

    insights = generate_insights(12)
    income_insight = next((i for i in insights if i["kind"] == "income_share"), None)
    assert income_insight is not None
    assert income_insight["params"]["category"] == "Restaurants"
