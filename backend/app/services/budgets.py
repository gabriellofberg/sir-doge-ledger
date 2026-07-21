"""Budget tracking, alerts, and savings goals."""

from __future__ import annotations

from typing import Any

from ..db import get_db, rows_to_dicts


def list_budgets() -> list[dict[str, Any]]:
    with get_db() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM budgets ORDER BY category").fetchall())


def upsert_budget(category: str, monthly_limit: float | None, *, enabled: bool = True) -> dict[str, Any]:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO budgets (category, monthly_limit, enabled, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(category) DO UPDATE SET
                monthly_limit = excluded.monthly_limit,
                enabled = excluded.enabled,
                updated_at = excluded.updated_at
            """,
            (category, monthly_limit, 1 if enabled else 0),
        )
        row = conn.execute("SELECT * FROM budgets WHERE category = ?", (category,)).fetchone()
        return dict(row)


def list_savings_goals() -> list[dict[str, Any]]:
    with get_db() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM savings_goals ORDER BY id").fetchall())


def upsert_savings_goal(
    goal_id: int | None,
    name: str,
    target_amount: float,
    current_amount: float,
) -> dict[str, Any]:
    with get_db() as conn:
        if goal_id:
            conn.execute(
                """
                UPDATE savings_goals
                SET name = ?, target_amount = ?, current_amount = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (name, target_amount, current_amount, goal_id),
            )
            row = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (goal_id,)).fetchone()
        else:
            cur = conn.execute(
                """
                INSERT INTO savings_goals (name, target_amount, current_amount, updated_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (name, target_amount, current_amount),
            )
            row = conn.execute("SELECT * FROM savings_goals WHERE id = ?", (cur.lastrowid,)).fetchone()
        return dict(row)


def budget_alerts(months: int = 3) -> list[dict[str, Any]]:
    """Compare recent month spend vs budget and prior month trend."""
    alerts: list[dict[str, Any]] = []
    with get_db() as conn:
        budgets = rows_to_dicts(conn.execute("SELECT * FROM budgets WHERE enabled = 1").fetchall())
        for b in budgets:
            cat = b["category"]
            limit = b.get("monthly_limit")
            if not limit:
                continue
            rows = conn.execute(
                """
                SELECT substr(tx_date, 1, 7) AS month,
                       ROUND(SUM(ABS(amount)), 2) AS spent
                FROM transactions
                WHERE amount < 0 AND category = ?
                GROUP BY substr(tx_date, 1, 7)
                ORDER BY month DESC
                LIMIT ?
                """,
                (cat, months + 1),
            ).fetchall()
            if not rows:
                continue
            current = float(rows[0]["spent"] or 0)
            prev = float(rows[1]["spent"] or 0) if len(rows) > 1 else 0
            if current > float(limit):
                alerts.append(
                    {
                        "kind": "over_budget",
                        "severity": "bad",
                        "category": cat,
                        "message_key": "alert.over_budget",
                        "month": rows[0]["month"],
                        "spent": current,
                        "limit": float(limit),
                    }
                )
            elif prev > 0 and current > prev * 1.2:
                alerts.append(
                    {
                        "kind": "spending_up",
                        "severity": "warn",
                        "category": cat,
                        "message_key": "alert.spending_up",
                        "month": rows[0]["month"],
                        "spent": current,
                        "prev_spent": prev,
                        "pct_change": round((current - prev) / prev * 100, 1),
                    }
                )
            elif prev > 0 and current < prev * 0.8:
                alerts.append(
                    {
                        "kind": "spending_down",
                        "severity": "good",
                        "category": cat,
                        "message_key": "alert.spending_down",
                        "month": rows[0]["month"],
                        "spent": current,
                        "prev_spent": prev,
                        "pct_change": round((current - prev) / prev * 100, 1),
                    }
                )
    return alerts
