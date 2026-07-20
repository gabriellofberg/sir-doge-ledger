from __future__ import annotations

from typing import Any

from ..db import get_db, now_iso, rows_to_dicts


def list_items(sort: str = "due") -> list[dict[str, Any]]:
    order = {
        "due": "CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC",
        "title": "title ASC",
        "kind": "kind ASC, title ASC",
    }.get(sort, "due_date ASC")
    with get_db() as conn:
        return rows_to_dicts(conn.execute(f"SELECT * FROM life_items ORDER BY {order}").fetchall())


def export_ics() -> str:
    items = [i for i in list_items() if i.get("due_date")]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SirDoge Ledger//EN"]
    for item in items:
        due = item["due_date"].replace("-", "")
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:sir-doge-life-{item['id']}@local",
                f"DTSTART;VALUE=DATE:{due}",
                f"SUMMARY:{item['title']} ({item['kind']})",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def create_item(
    *,
    title: str,
    kind: str,
    due_date: str | None = None,
    amount: float | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    ts = now_iso()
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO life_items (title, kind, due_date, amount, notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, kind, due_date, amount, notes, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM life_items WHERE id = ?", (cur.lastrowid,)).fetchone())


def update_item(item_id: int, **fields: Any) -> dict[str, Any]:
    allowed = {"title", "kind", "due_date", "amount", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        raise ValueError("no fields")
    updates["updated_at"] = now_iso()
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [item_id]
    with get_db() as conn:
        conn.execute(f"UPDATE life_items SET {sets} WHERE id = ?", vals)
        row = conn.execute("SELECT * FROM life_items WHERE id = ?", (item_id,)).fetchone()
        if not row:
            raise KeyError("not found")
        return dict(row)


def delete_item(item_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM life_items WHERE id = ?", (item_id,))
