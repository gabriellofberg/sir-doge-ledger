from app.services.categorize import categorize
from app.services.money import list_transactions, tx_hash
from app.services.normalize import (
    clean_match_text,
    group_key,
    merchant_key,
    normalize_merchant,
    phrase_matches,
)
from app.services.recurring import detect_recurring


def test_normalize_strips_noise():
    assert "SPOTIFY" in normalize_merchant("SPOTIFY AB KORTKÖP")


def test_merchant_key_strips_bank_date():
    assert merchant_key("Kortköp 260715 SJ Stockholm") == "SJ STOCKHOLM"
    assert merchant_key("Kortköp 260709 HINOYA") == "HINOYA"
    assert clean_match_text("260712 SONGSTERR COM") == "SONGSTERR COM"


def test_group_key_first_token():
    assert group_key("Kortköp 260715 SJ Stockholm") == "SJ"
    assert group_key("Kortköp Västtrafik") == "VÄSTTRAFIK"
    assert group_key("Swish till Oliwer") == "SWISH"


def test_phrase_matches_token_not_substring():
    assert phrase_matches("SJ", "Kortköp 260715 SJ GBG")
    assert phrase_matches("VÄSTTRAFIK", "Kortköp Västtrafik Göteborg")
    assert phrase_matches("VASTTRAFIK", "Kortköp Västtrafik Göteborg")
    assert phrase_matches("TOO GOOD TO GO", "Kortköp 260719 Too Good To Go")
    assert phrase_matches("SWISH", "Swish till Erik")
    assert not phrase_matches("SJ", "Kortköp TESLA SUPERCHARGER")


def test_categorize_spotify():
    r = categorize("SPOTIFY AB", -109.0, [])
    assert r.category == "Subscriptions"
    assert r.needs_review is False


def test_categorize_sj_and_vasttrafik_builtin():
    assert categorize("Kortköp 260720 SJ", -245.0, []).category == "Transport"
    assert categorize("Kortköp VÄSTTRAFIK", -39.0, []).category == "Transport"


def test_categorize_swish_payment_is_expense():
    r = categorize("Swish betalning Erik Engebretsen", -6500.0, [])
    assert r.category == "Other"
    assert r.source == "auto"
    assert r.needs_review is False
    assert categorize("Swish till Oliwer", -100.0, []).category == "Other"


def test_categorize_internal_transfer_stays_transfer():
    assert categorize("Överföring 3058 22 82136", 15000.0, []).category == "Transfers"
    assert categorize("Xtraspar", -10.0, []).category == "Transfers"
    assert categorize("Överföring sparkonto", -5000.0, []).category == "Transfers"


def test_categorize_incoming_swish_needs_review():
    r = categorize("Swish från Erik", 500.0, [])
    assert r.category == "Unclear"
    assert r.needs_review is True


def test_categorize_learned_rule_substring():
    rules = [("SJ", "Transport"), ("VASTTRAFIK", "Transport")]
    r = categorize("Kortköp 260718 SJ Stockholm C", -180.0, rules)
    assert r.category == "Transport"
    assert r.source == "learned"
    assert r.needs_review is False


def test_recurring_yearly():
    txs = []
    for month in range(1, 7):
        txs.append(
            {
                "tx_date": f"2026-{month:02d}-05",
                "amount": -109.0,
                "raw_description": "SPOTIFY AB",
                "normalized_merchant": "SPOTIFY",
                "category": "Subscriptions",
            }
        )
    groups = detect_recurring(txs)
    assert groups
    assert groups[0].cadence == "monthly"
    assert abs(groups[0].yearly_cost - 109 * 12) < 1


def test_recurring_rejects_two_same_week_purchases():
    txs = [
        {
            "tx_date": "2026-07-10",
            "amount": -26.0,
            "raw_description": "Kortköp 260710 Pressbyran",
            "normalized_merchant": "PRESSBYRAN",
            "category": "Other",
        },
        {
            "tx_date": "2026-07-11",
            "amount": -26.0,
            "raw_description": "Kortköp 260711 Pressbyran",
            "normalized_merchant": "PRESSBYRAN",
            "category": "Other",
        },
    ]
    assert detect_recurring(txs) == []


def test_recurring_rejects_transfers():
    txs = [
        {
            "tx_date": f"2026-{m:02d}-01",
            "amount": -200.0,
            "raw_description": "Swish till Erik",
            "normalized_merchant": "SWISH TILL ERIK",
            "category": "Transfers",
        }
        for m in range(1, 6)
    ]
    assert detect_recurring(txs) == []


def test_recurring_accepts_three_monthly_same_day():
    txs = [
        {
            "tx_date": f"2026-{m:02d}-12",
            "amount": -99.0,
            "raw_description": "NETFLIX.COM",
            "normalized_merchant": "NETFLIX COM",
            "category": "Subscriptions",
        }
        for m in (1, 2, 3)
    ]
    groups = detect_recurring(txs)
    assert len(groups) == 1
    assert groups[0].cadence == "monthly"
    assert groups[0].occurrence_count == 3


def test_foodora_small_order_is_restaurants():
    r = categorize("Kortköp 260710 Foodora", -189.0, [], foodora_threshold=350)
    assert r.category == "Restaurants"
    assert r.needs_review is False


def test_foodora_large_order_is_groceries():
    r = categorize("Kortköp 260710 Foodora", -520.0, [], foodora_threshold=350)
    assert r.category == "Groceries"
    assert r.needs_review is False


def test_foodora_threshold_boundary():
    r = categorize("Kortköp 260710 Foodora", -350.0, [], foodora_threshold=350)
    assert r.category == "Groceries"


def test_foodora_market_stays_groceries_regardless_of_amount():
    r = categorize("Kortköp 260710 Foodora Market", -99.0, [], foodora_threshold=350)
    assert r.category == "Groceries"


def test_foodora_learned_rule_overrides_threshold():
    rules = [("FOODORA", "Restaurants")]
    r = categorize("Kortköp 260710 Foodora", -999.0, rules, foodora_threshold=350)
    assert r.category == "Restaurants"
    assert r.source == "learned"


def _seed_tx(conn, *, tx_date: str, amount: float, desc: str, category: str) -> None:
    from app.db import now_iso

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
        ) VALUES (?, ?, ?, ?, ?, ?, 'auto', 0.9, 0, ?, ?)
        """,
        (
            iid,
            tx_date,
            amount,
            desc,
            desc.upper(),
            category,
            tx_hash(tx_date, amount, desc),
            now_iso(),
        ),
    )


def test_list_transactions_filters_month_and_category():
    from app.db import get_db

    with get_db() as conn:
        conn.execute("DELETE FROM transactions")
        _seed_tx(conn, tx_date="2026-05-10", amount=-200, desc="ZALANDO", category="Shopping")
        _seed_tx(conn, tx_date="2026-05-20", amount=-50, desc="ICA", category="Groceries")
        _seed_tx(conn, tx_date="2026-06-01", amount=-300, desc="HM", category="Shopping")

    rows = list_transactions(month="2026-05", category="Shopping")
    assert len(rows) == 1
    assert rows[0]["raw_description"] == "ZALANDO"


def test_list_transactions_sort_amount_desc():
    from app.db import get_db

    with get_db() as conn:
        conn.execute("DELETE FROM transactions")
        _seed_tx(conn, tx_date="2026-05-01", amount=-100, desc="SMALL", category="Shopping")
        _seed_tx(conn, tx_date="2026-05-02", amount=-900, desc="BIG", category="Shopping")

    rows = list_transactions(category="Shopping", sort="amount_desc")
    assert [r["raw_description"] for r in rows] == ["BIG", "SMALL"]


def test_list_transactions_sort_date_asc():
    from app.db import get_db

    with get_db() as conn:
        conn.execute("DELETE FROM transactions")
        _seed_tx(conn, tx_date="2026-05-31", amount=-10, desc="LATE", category="Shopping")
        _seed_tx(conn, tx_date="2026-05-01", amount=-10, desc="EARLY", category="Shopping")

    rows = list_transactions(category="Shopping", sort="date_asc")
    assert [r["raw_description"] for r in rows] == ["EARLY", "LATE"]


def test_recategorize_swish_transfers_on_startup():
    from app.db import get_db
    from app.services.money import _recategorize_swish_transfers

    with get_db() as conn:
        conn.execute("DELETE FROM transactions")
        _seed_tx(
            conn,
            tx_date="2026-07-16",
            amount=-6500.0,
            desc="Swish betalning Erik",
            category="Transfers",
        )
        _seed_tx(conn, tx_date="2026-07-17", amount=-10.0, desc="Xtraspar", category="Transfers")

    with get_db() as conn:
        updated = _recategorize_swish_transfers(conn)

    assert updated == 1
    with get_db() as conn:
        swish = conn.execute(
            "SELECT category FROM transactions WHERE raw_description LIKE 'Swish%'"
        ).fetchone()
        xtra = conn.execute(
            "SELECT category FROM transactions WHERE raw_description = 'Xtraspar'"
        ).fetchone()
    assert swish["category"] == "Other"
    assert xtra["category"] == "Transfers"
