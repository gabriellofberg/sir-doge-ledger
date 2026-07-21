"""Spending recommendations based on income and category norms."""

from __future__ import annotations

from typing import Any

from ..db import get_db
from .settings import get_setting


# Rough guideline % of net income (Swedish personal finance heuristics)
GUIDELINES: dict[str, tuple[float, float]] = {
    "Housing": (25, 30),
    "Groceries": (10, 15),
    "Transport": (5, 12),
    "Subscriptions": (3, 8),
    "Restaurants": (3, 8),
    "Shopping": (3, 10),
    "Health": (2, 8),
    "Savings": (10, 20),
}


def recommendations() -> list[dict[str, Any]]:
    income = float(get_setting("monthly_income") or 0)
    if income <= 0:
        return [
            {
                "kind": "set_income",
                "severity": "info",
                "message_key": "reco.set_income",
            }
        ]
    out: list[dict[str, Any]] = []
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT category,
                   ROUND(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 2) AS spent,
                   COUNT(*) AS tx_count
            FROM transactions
            WHERE tx_date >= date('now', '-30 days')
            GROUP BY category
            """
        ).fetchall()
    spent_by_cat = {r["category"]: float(r["spent"] or 0) for r in rows}
    housing = spent_by_cat.get("Housing", 0)
    if housing > income * 0.3:
        out.append(
            {
                "kind": "housing_high",
                "severity": "warn",
                "message_key": "reco.housing_high",
                "pct": round(housing / income * 100, 1),
                "spent": housing,
                "income": income,
            }
        )
    for cat, (lo, hi) in GUIDELINES.items():
        if cat == "Housing":
            continue
        spent = spent_by_cat.get(cat, 0)
        if spent <= 0:
            continue
        pct = spent / income * 100
        if pct > hi:
            out.append(
                {
                    "kind": "category_high",
                    "severity": "warn",
                    "message_key": "reco.category_high",
                    "category": cat,
                    "pct": round(pct, 1),
                    "guideline_hi": hi,
                    "spent": spent,
                }
            )
        elif pct < lo and spent > 0:
            out.append(
                {
                    "kind": "category_low",
                    "severity": "good",
                    "message_key": "reco.category_low",
                    "category": cat,
                    "pct": round(pct, 1),
                    "guideline_lo": lo,
                    "spent": spent,
                }
            )
    return out
