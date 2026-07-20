from app.services.categorize import categorize
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


def test_categorize_swish_builtin():
    assert categorize("Swish till Oliwer", -100.0, []).category == "Transfers"


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
