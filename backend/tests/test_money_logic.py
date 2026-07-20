from app.services.categorize import categorize
from app.services.normalize import normalize_merchant
from app.services.recurring import detect_recurring


def test_normalize_strips_noise():
    assert "SPOTIFY" in normalize_merchant("SPOTIFY AB KORTKÖP")


def test_categorize_spotify():
    r = categorize("SPOTIFY AB", -109.0, [])
    assert r.category == "Subscriptions"
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
