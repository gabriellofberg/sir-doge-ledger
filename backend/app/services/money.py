"""Service layer for money features."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..config import MAX_IMPORT_ROWS, MAX_TRANSACTION_LIMIT, MAX_UPLOAD_BYTES, ensure_dirs
from ..db import get_db, now_iso, rows_to_dicts
from .categorize import categorize, ensure_category
from .import_parse import ColumnMapping, guess_mapping, parse_all_rows, read_tabular
from .import_sessions import delete_session, get_session_path
from .normalize import merchant_key, normalize_merchant
from .recurring import detect_recurring
from .security_paths import escape_like_pattern

TRANSFER_CAT = "Transfers"
INCOME_CAT = "Income"


def tx_hash(tx_date: str, amount: float, description: str) -> str:
    payload = f"{tx_date}|{amount:.2f}|{description.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def list_learned_rules(conn) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT match_text, category FROM category_rules WHERE enabled = 1 ORDER BY length(match_text) DESC"
    ).fetchall()
    return [(r["match_text"], r["category"]) for r in rows]


def preview_file(path: Path) -> dict[str, Any]:
    headers, preview, delimiter = read_tabular(path)
    return {
        "headers": headers,
        "preview_rows": preview,
        "delimiter": delimiter,
        "guessed_mapping": guess_mapping(headers),
    }


def commit_import_session(
    session_id: str,
    mapping: ColumnMapping,
    filename: str,
    *,
    delete_upload: bool = True,
) -> dict[str, Any]:
    path = get_session_path(session_id)
    if path.stat().st_size > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    rows = parse_all_rows(path, mapping)
    inserted = 0
    skipped = 0
    unclear = 0
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO imports (filename, imported_at, row_count, mapping_json) VALUES (?, ?, ?, ?)",
            (
                filename,
                now_iso(),
                len(rows),
                json.dumps(
                    {
                        "date": mapping.date,
                        "amount": mapping.amount,
                        "description": mapping.description,
                        "date_format": mapping.date_format,
                        "amount_decimal": mapping.amount_decimal,
                        "delimiter": mapping.delimiter,
                    }
                ),
            ),
        )
        import_id = cur.lastrowid
        learned = list_learned_rules(conn)
        for r in rows:
            h = tx_hash(r.tx_date, r.amount, r.description)
            exists = conn.execute(
                "SELECT id FROM transactions WHERE tx_hash = ?", (h,)
            ).fetchone()
            if exists:
                skipped += 1
                continue
            cat = categorize(r.description, r.amount, learned)
            if cat.needs_review:
                unclear += 1
            conn.execute(
                """
                INSERT INTO transactions (
                    import_id, tx_date, amount, raw_description, normalized_merchant,
                    category, category_source, confidence, needs_review, tx_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    import_id,
                    r.tx_date,
                    r.amount,
                    r.description,
                    normalize_merchant(r.description),
                    cat.category,
                    cat.source,
                    cat.confidence,
                    1 if cat.needs_review else 0,
                    h,
                    now_iso(),
                ),
            )
            inserted += 1
        _refresh_recurring(conn)
    delete_session(session_id, remove_file=delete_upload)
    return {
        "import_id": import_id,
        "row_count": inserted,
        "skipped_count": skipped,
        "unclear_count": unclear,
    }


def _refresh_recurring(conn) -> None:
    txs = rows_to_dicts(
        conn.execute(
            "SELECT id, tx_date, amount, raw_description, normalized_merchant, category FROM transactions"
        ).fetchall()
    )
    candidates = detect_recurring(txs)
    existing = {
        (r["normalized_merchant"], r["cadence"], round(r["typical_amount"], 2)): r
        for r in conn.execute("SELECT * FROM recurring_groups").fetchall()
    }
    for c in candidates:
        key = (c.normalized_merchant, c.cadence, round(c.typical_amount, 2))
        prev = existing.get(key)
        if prev:
            conn.execute(
                """
                UPDATE recurring_groups
                SET name = ?, yearly_cost = ?, occurrence_count = ?, last_seen = ?, updated_at = ?
                WHERE id = ?
                """,
                (c.name, c.yearly_cost, c.occurrence_count, c.last_seen, now_iso(), prev["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO recurring_groups (
                    name, normalized_merchant, cadence, typical_amount, yearly_cost,
                    occurrence_count, last_seen, decision, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    c.name,
                    c.normalized_merchant,
                    c.cadence,
                    c.typical_amount,
                    c.yearly_cost,
                    c.occurrence_count,
                    c.last_seen,
                    now_iso(),
                ),
            )


def _date_cutoff(months: int) -> str:
    today = date.today()
    start = today.replace(day=1)
    for _ in range(months - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    return start.isoformat()


def list_transactions(
    *,
    needs_review: bool | None = None,
    income_review: bool | None = None,
    category: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    month: str | None = None,
    limit: int = 500,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, MAX_TRANSACTION_LIMIT))
    offset = max(0, offset)
    clauses: list[str] = []
    params: list[Any] = []
    if needs_review is True:
        clauses.append("t.needs_review = 1")
    if needs_review is False:
        clauses.append("t.needs_review = 0")
    if income_review is True:
        clauses.append("t.amount > 0")
        clauses.append(f"t.category NOT IN ('{INCOME_CAT}', '{TRANSFER_CAT}')")
    if category:
        clauses.append("t.category = ?")
        params.append(category)
    if search:
        clauses.append("(t.raw_description LIKE ? OR t.normalized_merchant LIKE ?)")
        q = f"%{search.strip()}%"
        params.extend([q, q])
    if month:
        clauses.append("substr(t.tx_date, 1, 7) = ?")
        params.append(month.strip())
    if tag:
        clauses.append(
            "EXISTS (SELECT 1 FROM transaction_tags tt WHERE tt.transaction_id = t.id AND tt.tag = ?)"
        )
        params.append(tag.strip().lower())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    with get_db() as conn:
        rows = conn.execute(
            f"""
            SELECT t.*, (
                SELECT GROUP_CONCAT(tag, ',') FROM transaction_tags tt
                WHERE tt.transaction_id = t.id
            ) AS tags_csv
            FROM transactions t
            {where}
            ORDER BY t.tx_date DESC, t.id DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        out = rows_to_dicts(rows)
        for row in out:
            raw = row.pop("tags_csv", None) or ""
            row["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
        return out


def category_summary() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT category,
                   COUNT(*) AS tx_count,
                   ROUND(SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END), 2) AS spent,
                   ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) AS income,
                   SUM(needs_review) AS unclear_count
            FROM transactions
            GROUP BY category
            ORDER BY spent ASC
            """
        ).fetchall()
        return rows_to_dicts(rows)


def cashflow(months: int = 12) -> list[dict[str, Any]]:
    cutoff = _date_cutoff(months)
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT substr(tx_date, 1, 7) AS month,
                   ROUND(SUM(CASE WHEN amount > 0 AND category != ? THEN amount ELSE 0 END), 2) AS income,
                   ROUND(SUM(CASE WHEN amount < 0 AND category != ? THEN amount ELSE 0 END), 2) AS spent,
                   ROUND(SUM(CASE WHEN category = ? THEN ABS(amount) ELSE 0 END), 2) AS transfer_volume,
                   SUM(CASE WHEN needs_review = 1 THEN 1 ELSE 0 END) AS unclear_count
            FROM transactions
            WHERE tx_date >= ?
            GROUP BY substr(tx_date, 1, 7)
            ORDER BY month ASC
            """,
            (TRANSFER_CAT, TRANSFER_CAT, TRANSFER_CAT, cutoff),
        ).fetchall()
    out = []
    for r in rows:
        income = float(r["income"] or 0)
        spent = float(r["spent"] or 0)
        out.append(
            {
                "month": r["month"],
                "income": income,
                "spent": spent,
                "net": round(income + spent, 2),
                "transfer_volume": float(r["transfer_volume"] or 0),
                "unclear_count": int(r["unclear_count"] or 0),
            }
        )
    return out


def breakdown(kind: str = "spent") -> list[dict[str, Any]]:
    if kind == "income":
        sql = """
            SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS tx_count
            FROM transactions
            WHERE amount > 0 AND category NOT IN (?, 'Unclear')
            GROUP BY category
            ORDER BY total DESC
        """
    else:
        sql = """
            SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS tx_count
            FROM transactions
            WHERE amount < 0 AND category NOT IN (?, 'Unclear')
            GROUP BY category
            ORDER BY total ASC
        """
    with get_db() as conn:
        return rows_to_dicts(conn.execute(sql, (TRANSFER_CAT,)).fetchall())


def completeness() -> dict[str, Any]:
    stats = money_stats()
    with get_db() as conn:
        uncategorized_income = conn.execute(
            """
            SELECT COUNT(*) AS c FROM transactions
            WHERE amount > 0 AND category NOT IN (?, ?)
            """,
            (INCOME_CAT, TRANSFER_CAT),
        ).fetchone()["c"]
    return {
        **stats,
        "uncategorized_income_count": int(uncategorized_income),
    }


def update_transaction_category(
    tx_id: int,
    category: str,
    *,
    remember: bool,
    match_text: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    category = ensure_category(category)
    with get_db() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if not row:
            raise KeyError("transaction not found")
        source = "manual_once"
        if remember:
            key = (match_text or merchant_key(row["raw_description"])).upper().strip()
            conn.execute(
                """
                INSERT INTO category_rules (match_text, category, enabled, created_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(match_text) DO UPDATE SET category = excluded.category, enabled = 1
                """,
                (key, category, now_iso()),
            )
            source = "learned"
            like_key = escape_like_pattern(key)
            conn.execute(
                """
                UPDATE transactions
                SET category = ?, category_source = 'learned', confidence = 0.95, needs_review = 0
                WHERE normalized_merchant LIKE ? ESCAPE '\\' OR normalized_merchant = ?
                """,
                (category, f"%{like_key}%", key),
            )
        conn.execute(
            """
            UPDATE transactions
            SET category = ?, category_source = ?, confidence = 1.0, needs_review = 0
            WHERE id = ?
            """,
            (category, source, tx_id),
        )
        if notes is not None:
            conn.execute("UPDATE transactions SET notes = ? WHERE id = ?", (notes, tx_id))
        if tags is not None:
            _set_tags(conn, tx_id, tags)
        updated = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        out = dict(updated)
        out["tags"] = _get_tags(conn, tx_id)
        return out


def list_recurring() -> list[dict[str, Any]]:
    with get_db() as conn:
        _refresh_recurring(conn)
        return rows_to_dicts(
            conn.execute("SELECT * FROM recurring_groups ORDER BY yearly_cost DESC").fetchall()
        )


def update_recurring(
    group_id: int,
    *,
    decision: str | None = None,
    use_it: str | None = None,
    worth_it: str | None = None,
    name: str | None = None,
    cancel_by: str | None = None,
) -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM recurring_groups WHERE id = ?", (group_id,)).fetchone()
        if not row:
            raise KeyError("not found")
        decision = decision if decision is not None else row["decision"]
        use_it = use_it if use_it is not None else row["use_it"]
        worth_it = worth_it if worth_it is not None else row["worth_it"]
        name = name if name is not None else row["name"]
        cancel_by = cancel_by if cancel_by is not None else row["cancel_by"]
        conn.execute(
            """
            UPDATE recurring_groups
            SET decision = ?, use_it = ?, worth_it = ?, name = ?, cancel_by = ?, updated_at = ?
            WHERE id = ?
            """,
            (decision, use_it, worth_it, name, cancel_by, now_iso(), group_id),
        )
        return dict(conn.execute("SELECT * FROM recurring_groups WHERE id = ?", (group_id,)).fetchone())


def list_rules() -> list[dict[str, Any]]:
    with get_db() as conn:
        return rows_to_dicts(
            conn.execute("SELECT * FROM category_rules ORDER BY created_at DESC").fetchall()
        )


def delete_rule(rule_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM category_rules WHERE id = ?", (rule_id,))


def money_stats() -> dict[str, Any]:
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM transactions").fetchone()["c"]
        unclear = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE needs_review = 1"
        ).fetchone()["c"]
        pending_rec = conn.execute(
            "SELECT COUNT(*) AS c FROM recurring_groups WHERE decision = 'pending'"
        ).fetchone()["c"]
        spent = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS s FROM transactions
            WHERE amount < 0 AND category != ?
            """,
            (TRANSFER_CAT,),
        ).fetchone()["s"]
        income = conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS s FROM transactions
            WHERE amount > 0 AND category != ?
            """,
            (TRANSFER_CAT,),
        ).fetchone()["s"]
        transfer_volume = conn.execute(
            """
            SELECT COALESCE(SUM(ABS(amount)), 0) AS s FROM transactions WHERE category = ?
            """,
            (TRANSFER_CAT,),
        ).fetchone()["s"]
        yearly = conn.execute(
            "SELECT COALESCE(SUM(yearly_cost), 0) AS s FROM recurring_groups WHERE decision NOT IN ('ignore')"
        ).fetchone()["s"]
        uncategorized_income = conn.execute(
            """
            SELECT COUNT(*) AS c FROM transactions
            WHERE amount > 0 AND category NOT IN (?, ?)
            """,
            (INCOME_CAT, TRANSFER_CAT),
        ).fetchone()["c"]
        total_spent = round(float(spent), 2)
        total_income = round(float(income), 2)
        return {
            "transaction_count": total,
            "unclear_count": unclear,
            "pending_recurring": pending_rec,
            "total_spent": total_spent,
            "total_income": total_income,
            "net": round(total_income + total_spent, 2),
            "transfer_volume": round(float(transfer_volume), 2),
            "uncategorized_income_count": int(uncategorized_income),
            "recurring_yearly_total": round(float(yearly), 2),
        }


def _get_tags(conn, tx_id: int) -> list[str]:
    rows = conn.execute("SELECT tag FROM transaction_tags WHERE transaction_id = ?", (tx_id,)).fetchall()
    return [r["tag"] for r in rows]


def _set_tags(conn, tx_id: int, tags: list[str]) -> None:
    conn.execute("DELETE FROM transaction_tags WHERE transaction_id = ?", (tx_id,))
    for tag in {t.strip().lower() for t in tags if t.strip()}:
        conn.execute(
            "INSERT INTO transaction_tags (transaction_id, tag) VALUES (?, ?)", (tx_id, tag)
        )


def update_transaction_meta(
    tx_id: int, *, notes: str | None = None, tags: list[str] | None = None
) -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
        if not row:
            raise KeyError("transaction not found")
        if notes is not None:
            conn.execute("UPDATE transactions SET notes = ? WHERE id = ?", (notes, tx_id))
        if tags is not None:
            _set_tags(conn, tx_id, tags)
        out = dict(conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone())
        out["tags"] = _get_tags(conn, tx_id)
        return out


def create_manual_transaction(
    tx_date: str,
    amount: float,
    description: str,
    category: str,
    notes: str | None,
    tags: list[str],
) -> dict[str, Any]:
    category = ensure_category(category)
    h = tx_hash(tx_date, amount, description)
    with get_db() as conn:
        exists = conn.execute("SELECT id FROM transactions WHERE tx_hash = ?", (h,)).fetchone()
        if exists:
            raise ValueError("Duplicate transaction")
        cur = conn.execute(
            """
            INSERT INTO transactions (
                import_id, tx_date, amount, raw_description, normalized_merchant,
                category, category_source, confidence, needs_review, tx_hash, notes, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, 'manual', 1.0, 0, ?, ?, ?)
            """,
            (
                tx_date,
                amount,
                description,
                normalize_merchant(description),
                category,
                h,
                notes,
                now_iso(),
            ),
        )
        tx_id = cur.lastrowid
        _set_tags(conn, tx_id, tags)
        _refresh_recurring(conn)
        out = dict(conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone())
        out["tags"] = tags
        return out


def bulk_update_category(ids: list[int], category: str, remember: bool) -> int:
    category = ensure_category(category)
    updated = 0
    for tx_id in ids:
        try:
            update_transaction_category(tx_id, category, remember=remember)
            updated += 1
        except KeyError:
            continue
    return updated


def list_imports() -> list[dict[str, Any]]:
    with get_db() as conn:
        return rows_to_dicts(
            conn.execute("SELECT * FROM imports ORDER BY imported_at DESC LIMIT 50").fetchall()
        )


def list_bank_profiles() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = rows_to_dicts(conn.execute("SELECT * FROM bank_profiles ORDER BY name").fetchall())
        for row in rows:
            try:
                row["mapping"] = json.loads(row.pop("mapping_json", "{}"))
            except json.JSONDecodeError:
                row["mapping"] = {}
        return rows


def save_bank_profile(name: str, mapping: dict[str, Any]) -> dict[str, Any]:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO bank_profiles (name, mapping_json, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET mapping_json = excluded.mapping_json
            """,
            (name.strip(), json.dumps(mapping), now_iso()),
        )
        row = conn.execute("SELECT * FROM bank_profiles WHERE name = ?", (name.strip(),)).fetchone()
        out = dict(row)
        out["mapping"] = mapping
        return out


def delete_bank_profile(profile_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM bank_profiles WHERE id = ?", (profile_id,))


def update_rule(rule_id: int, *, category: str | None = None, enabled: bool | None = None) -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM category_rules WHERE id = ?", (rule_id,)).fetchone()
        if not row:
            raise KeyError("not found")
        cat = ensure_category(category) if category else row["category"]
        en = row["enabled"] if enabled is None else (1 if enabled else 0)
        conn.execute(
            "UPDATE category_rules SET category = ?, enabled = ? WHERE id = ?",
            (cat, en, rule_id),
        )
        return dict(conn.execute("SELECT * FROM category_rules WHERE id = ?", (rule_id,)).fetchone())


def _detect_price_changes(conn) -> None:
    rows = conn.execute(
        """
        SELECT normalized_merchant, ABS(amount) AS amt, tx_date
        FROM transactions
        WHERE amount < 0
        ORDER BY normalized_merchant, tx_date
        """
    ).fetchall()
    by_merchant: dict[str, list[float]] = {}
    for r in rows:
        by_merchant.setdefault(r["normalized_merchant"], []).append(float(r["amt"]))
    for merchant, amounts in by_merchant.items():
        if len(amounts) < 3:
            continue
        typical = sorted(set(round(a, 2) for a in amounts))
        if len(typical) < 2:
            continue
        old, new = typical[-2], typical[-1]
        if old <= 0 or new <= old * 1.08:
            continue
        exists = conn.execute(
            """
            SELECT id FROM recurring_price_events
            WHERE normalized_merchant = ? AND old_amount = ? AND new_amount = ?
            """,
            (merchant, old, new),
        ).fetchone()
        if not exists:
            conn.execute(
                """
                INSERT INTO recurring_price_events
                (normalized_merchant, old_amount, new_amount, detected_at)
                VALUES (?, ?, ?, ?)
                """,
                (merchant, old, new, now_iso()),
            )


def price_alerts() -> list[dict[str, Any]]:
    with get_db() as conn:
        _detect_price_changes(conn)
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT * FROM recurring_price_events
                WHERE acknowledged = 0
                ORDER BY detected_at DESC
                LIMIT 20
                """
            ).fetchall()
        )
    for row in rows:
        row["pct_change"] = round((row["new_amount"] - row["old_amount"]) / row["old_amount"] * 100, 1)
    return rows


def recurring_yearly_total() -> float:
    with get_db() as conn:
        val = conn.execute(
            "SELECT COALESCE(SUM(yearly_cost), 0) AS s FROM recurring_groups WHERE decision NOT IN ('ignore')"
        ).fetchone()["s"]
        return round(float(val), 2)


def year_comparison() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT substr(tx_date, 1, 4) AS year,
                   category,
                   ROUND(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 2) AS spent
            FROM transactions
            WHERE amount < 0
            GROUP BY substr(tx_date, 1, 4), category
            ORDER BY year DESC, spent DESC
            """
        ).fetchall()
    by_year: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_year.setdefault(r["year"], []).append({"category": r["category"], "spent": float(r["spent"])})
    return [{"year": y, "categories": cats} for y, cats in sorted(by_year.items(), reverse=True)]
