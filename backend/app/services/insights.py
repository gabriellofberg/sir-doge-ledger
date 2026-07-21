"""Actionable and interesting financial insights for the dashboard."""

from __future__ import annotations

from typing import Any

from ..db import get_db, rows_to_dicts
from .budgets import budget_alerts
from .money import TRANSFER_CAT, _date_cutoff, breakdown, cashflow, year_comparison
from .recommendations import GUIDELINES
from .settings import get_setting

EXCLUDED_CATS = {TRANSFER_CAT, "Income", "Unclear"}
DISCRETIONARY_CATS = {"Restaurants", "Shopping", "Entertainment", "Subscriptions"}
SAVINGS_REDUCTION_PCT = 20
MAX_INSIGHTS = 5


def _budget_insights(months: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for alert in budget_alerts(months):
        kind = alert.get("kind")
        score = {"over_budget": 100, "spending_up": 90, "spending_down": 60}.get(str(kind), 70)
        params = {k: v for k, v in alert.items() if k not in ("kind", "severity", "message_key")}
        out.append(
            {
                "kind": kind,
                "severity": alert.get("severity", "warn"),
                "score": score,
                "params": params,
                "link": f"/transactions?category={alert.get('category', '')}",
            }
        )
    return out


def generate_insights(months: int = 12) -> list[dict[str, Any]]:
    months = max(1, min(int(months), 36))
    candidates: list[dict[str, Any]] = []
    candidates.extend(_budget_insights(months))

    cats = breakdown("spent", months=months)
    total_spent = sum(abs(float(c["total"])) for c in cats)
    if total_spent <= 0:
        return sorted(candidates, key=lambda x: x["score"], reverse=True)[:MAX_INSIGHTS]

    disc = [c for c in cats if c["category"] in DISCRETIONARY_CATS]
    if not disc:
        disc = [c for c in cats if c["category"] not in EXCLUDED_CATS]

    if disc:
        top = max(disc, key=lambda c: abs(float(c["total"])))
        spent = abs(float(top["total"]))
        annualized = spent * (12 / months) if months < 12 else spent
        savings = round(annualized * SAVINGS_REDUCTION_PCT / 100)
        if savings >= 100:
            candidates.append(
                {
                    "kind": "savings_scenario",
                    "severity": "info",
                    "score": int(min(95, 50 + savings / 100)),
                    "params": {
                        "category": top["category"],
                        "spent": round(spent),
                        "months": months,
                        "reduction_pct": SAVINGS_REDUCTION_PCT,
                        "savings": savings,
                    },
                    "link": f"/transactions?category={top['category']}",
                }
            )

    cutoff = _date_cutoff(months)
    with get_db() as conn:
        merchant_row = conn.execute(
            """
            SELECT normalized_merchant, ROUND(SUM(ABS(amount)), 2) AS spent
            FROM transactions
            WHERE amount < 0
              AND category NOT IN ('Transfers', 'Unclear', 'Income')
              AND tx_date >= ?
            GROUP BY normalized_merchant
            ORDER BY spent DESC
            LIMIT 1
            """,
            (cutoff,),
        ).fetchone()

    if merchant_row:
        m_spent = float(merchant_row["spent"])
        m_pct = round(m_spent / total_spent * 100)
        if m_spent >= 500:
            candidates.append(
                {
                    "kind": "top_merchant",
                    "severity": "info",
                    "score": int(min(85, 40 + m_spent / 200)),
                    "params": {
                        "merchant": merchant_row["normalized_merchant"],
                        "spent": round(m_spent),
                        "pct": m_pct,
                    },
                    "link": f"/transactions?search={merchant_row['normalized_merchant']}",
                }
            )

    spend_cats = [c for c in cats if c["category"] not in EXCLUDED_CATS]
    if spend_cats:
        top_cat = max(spend_cats, key=lambda c: abs(float(c["total"])))
        cat_spent = abs(float(top_cat["total"]))
        cat_pct = round(cat_spent / total_spent * 100)
        if cat_pct >= 15:
            candidates.append(
                {
                    "kind": "category_share",
                    "severity": "info",
                    "score": int(min(75, 30 + cat_pct)),
                    "params": {
                        "category": top_cat["category"],
                        "pct": cat_pct,
                        "spent": round(cat_spent),
                    },
                    "link": f"/transactions?category={top_cat['category']}",
                }
            )

    income = float(get_setting("monthly_income") or 0)
    if income > 0:
        for cat_row in sorted(spend_cats, key=lambda c: abs(float(c["total"])), reverse=True):
            cat = cat_row["category"]
            if cat not in GUIDELINES:
                continue
            spent_monthly = abs(float(cat_row["total"])) / months
            pct = round(spent_monthly / income * 100, 1)
            hi = GUIDELINES[cat][1]
            if pct > hi:
                candidates.append(
                    {
                        "kind": "income_share",
                        "severity": "warn",
                        "score": int(min(92, 60 + (pct - hi) * 3)),
                        "params": {
                            "category": cat,
                            "pct": pct,
                            "guideline_hi": hi,
                            "spent_monthly": round(spent_monthly),
                        },
                        "link": f"/transactions?category={cat}",
                    }
                )
                break

    cf = cashflow(max(months, 2))
    if len(cf) >= 2:
        prev = cf[-2]
        curr = cf[-1]
        prev_spent = abs(float(prev["spent"]))
        curr_spent = abs(float(curr["spent"]))
        if prev_spent > 0:
            pct_change = round((curr_spent - prev_spent) / prev_spent * 100, 1)
            if abs(pct_change) >= 8:
                candidates.append(
                    {
                        "kind": "mom_trend",
                        "severity": "warn" if pct_change > 0 else "good",
                        "score": int(min(80, 45 + abs(pct_change))),
                        "params": {
                            "pct": abs(pct_change),
                            "direction": "up" if pct_change > 0 else "down",
                            "month": curr["month"],
                        },
                        "link": None,
                    }
                )

    years_data = year_comparison()
    if len(years_data) >= 2:
        current_year = years_data[0]["year"]
        prev_year = years_data[1]["year"]
        prev_by_cat = {c["category"]: c["spent"] for c in years_data[1]["categories"]}
        for cat_row in years_data[0]["categories"]:
            cat = cat_row["category"]
            if cat in EXCLUDED_CATS:
                continue
            curr_spent = float(cat_row["spent"])
            prev_spent = float(prev_by_cat.get(cat, 0))
            if prev_spent > 500 and curr_spent > prev_spent * 1.15:
                pct = round((curr_spent - prev_spent) / prev_spent * 100)
                candidates.append(
                    {
                        "kind": "yoy_change",
                        "severity": "warn",
                        "score": int(min(78, 40 + pct / 2)),
                        "params": {
                            "category": cat,
                            "pct": pct,
                            "current_year": current_year,
                            "prev_year": prev_year,
                        },
                        "link": f"/transactions?category={cat}",
                    }
                )
                break

    with get_db() as conn:
        recurring = rows_to_dicts(
            conn.execute(
                """
                SELECT name, yearly_cost FROM recurring_groups
                WHERE decision NOT IN ('ignore')
                ORDER BY yearly_cost DESC
                """
            ).fetchall()
        )
    if recurring:
        total_yearly = sum(float(r["yearly_cost"]) for r in recurring)
        if total_yearly >= 1000:
            candidates.append(
                {
                    "kind": "recurring_burden",
                    "severity": "info",
                    "score": int(min(82, 35 + total_yearly / 500)),
                    "params": {
                        "total": round(total_yearly),
                        "names": ", ".join(r["name"] for r in recurring[:3]),
                        "count": len(recurring),
                    },
                    "link": "/recurring",
                }
            )

    if cf:
        best = max(cf, key=lambda m: float(m["net"]))
        if float(best["net"]) > 0:
            candidates.append(
                {
                    "kind": "best_month",
                    "severity": "good",
                    "score": 55,
                    "params": {
                        "month": best["month"],
                        "net": round(float(best["net"])),
                    },
                    "link": None,
                }
            )

    budget_kinds = {"over_budget", "spending_up", "spending_down"}
    seen_kinds: set[str] = set()
    filtered: list[dict[str, Any]] = []
    for item in sorted(candidates, key=lambda x: x["score"], reverse=True):
        kind = str(item["kind"])
        if kind in budget_kinds:
            filtered.append(item)
            continue
        if kind in seen_kinds:
            continue
        seen_kinds.add(kind)
        filtered.append(item)

    return sorted(filtered, key=lambda x: x["score"], reverse=True)[:MAX_INSIGHTS]
