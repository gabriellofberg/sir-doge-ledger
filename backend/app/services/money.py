"""Service layer for money features."""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from ..config import MAX_TRANSACTION_LIMIT, MAX_UPLOAD_BYTES
from ..db import get_db, now_iso, rows_to_dicts
from .categorize import (
    _DEFAULT_FOODORA_THRESHOLD,
    categorize,
    ensure_category,
    is_swish_payment,
    resolve_transfer_kind,
)
from .import_parse import ColumnMapping, guess_mapping, parse_all_rows, read_tabular
from .import_sessions import delete_session, get_session_path
from .normalize import clean_match_text, group_key, merchant_key, normalize_merchant, phrase_matches
from .recurring import detect_recurring
from .settings import get_setting

TRANSFER_CAT = "Transfers"
INCOME_CAT = "Income"

_SORT_OPTIONS: dict[str, str] = {
    "date_desc": "t.tx_date DESC, t.id DESC",
    "date_asc": "t.tx_date ASC, t.id ASC",
    "amount_desc": "ABS(t.amount) DESC, t.id DESC",
    "amount_asc": "ABS(t.amount) ASC, t.id ASC",
    "description_asc": "t.raw_description ASC, t.id ASC",
    "description_desc": "t.raw_description DESC, t.id DESC",
}


def tx_hash(tx_date: str, amount: float, description: str) -> str:
    payload = f"{tx_date}|{amount:.2f}|{description.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def list_learned_rules(conn) -> list[tuple[str, str]]:
    rows = conn.execute(
        "SELECT match_text, category FROM category_rules WHERE enabled = 1 ORDER BY length(match_text) DESC"
    ).fetchall()
    return [(r["match_text"], r["category"]) for r in rows]


def apply_rule_to_existing(conn, match_text: str, category: str) -> int:
    """Recategorize existing transactions whose description matches the rule phrase."""
    category = ensure_category(category)
    rows = conn.execute(
        "SELECT id, raw_description FROM transactions WHERE category_source != 'manual_once'"
    ).fetchall()
    updated = 0
    for row in rows:
        if not phrase_matches(match_text, row["raw_description"]):
            continue
        conn.execute(
            """
            UPDATE transactions
            SET category = ?, category_source = 'learned', confidence = 0.95, needs_review = 0,
                transfer_kind = ?
            WHERE id = ?
            """,
            (category, resolve_transfer_kind(category, row["raw_description"]), row["id"]),
        )
        updated += 1
    return updated


def reapply_all_learned_rules(conn) -> int:
    """Apply enabled rules (longest match first) to all non-manual transactions."""
    rules = list_learned_rules(conn)
    if not rules:
        return 0
    rows = conn.execute(
        "SELECT id, raw_description FROM transactions WHERE category_source != 'manual_once'"
    ).fetchall()
    updated = 0
    for row in rows:
        for match_text, category in rules:
            if phrase_matches(match_text, row["raw_description"]):
                conn.execute(
                    """
                    UPDATE transactions
                    SET category = ?, category_source = 'learned', confidence = 0.95, needs_review = 0,
                        transfer_kind = ?
                    WHERE id = ?
                    """,
                    (
                        ensure_category(category),
                        resolve_transfer_kind(category, row["raw_description"]),
                        row["id"],
                    ),
                )
                updated += 1
                break
    return updated


def sanitize_category_rules(conn) -> int:
    """Strip date/ref prefixes from stored match_text and re-apply enabled rules."""
    rows = conn.execute("SELECT id, match_text, category, enabled FROM category_rules").fetchall()
    changed = 0
    for row in rows:
        cleaned = clean_match_text(row["match_text"])
        if not cleaned or cleaned == row["match_text"]:
            continue
        conflict = conn.execute(
            "SELECT id FROM category_rules WHERE match_text = ? AND id != ?",
            (cleaned, row["id"]),
        ).fetchone()
        if conflict:
            conn.execute("DELETE FROM category_rules WHERE id = ?", (row["id"],))
        else:
            conn.execute(
                "UPDATE category_rules SET match_text = ? WHERE id = ?",
                (cleaned, row["id"]),
            )
        changed += 1
    reapply_all_learned_rules(conn)
    _recategorize_foodora(conn)
    _recategorize_swish_transfers(conn)
    return changed


def _recategorize_foodora(conn) -> int:
    """Re-evaluate Foodora transactions against the amount-based grocery threshold."""
    threshold = float(get_setting("foodora_grocery_threshold", _DEFAULT_FOODORA_THRESHOLD))
    rows = conn.execute(
        """
        SELECT id, raw_description, amount, category, category_source
        FROM transactions
        WHERE category_source NOT IN ('manual_once', 'learned')
          AND normalized_merchant LIKE '%FOODORA%'
        """
    ).fetchall()
    updated = 0
    for row in rows:
        amt = abs(float(row["amount"]))
        if amt >= threshold and row["category"] != "Groceries":
            conn.execute(
                "UPDATE transactions SET category = 'Groceries', category_source = 'auto', confidence = 0.9, needs_review = 0 WHERE id = ?",
                (row["id"],),
            )
            updated += 1
        elif amt < threshold and row["category"] != "Restaurants":
            conn.execute(
                "UPDATE transactions SET category = 'Restaurants', category_source = 'auto', confidence = 0.9, needs_review = 0 WHERE id = ?",
                (row["id"],),
            )
            updated += 1
    return updated


def _recategorize_swish_transfers(conn) -> int:
    """Move misclassified Swish payments out of Transfers (they are real expenses)."""
    rows = conn.execute(
        """
        SELECT id, raw_description, amount
        FROM transactions
        WHERE category = ?
          AND category_source NOT IN ('manual_once', 'learned')
        """,
        (TRANSFER_CAT,),
    ).fetchall()
    updated = 0
    for row in rows:
        if not is_swish_payment(row["raw_description"], float(row["amount"])):
            continue
        conn.execute(
            """
            UPDATE transactions
            SET category = 'Other', category_source = 'auto', confidence = 0.9, needs_review = 0
            WHERE id = ?
            """,
            (row["id"],),
        )
        updated += 1
    return updated


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
                    category, category_source, confidence, needs_review, tx_hash,
                    transfer_kind, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    cat.transfer_kind,
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
    existing_rows = list(conn.execute("SELECT * FROM recurring_groups").fetchall())
    existing = {
        (r["normalized_merchant"], r["cadence"], round(r["typical_amount"], 2)): r
        for r in existing_rows
    }
    seen_keys: set[tuple[str, str, float]] = set()
    for c in candidates:
        key = (c.normalized_merchant, c.cadence, round(c.typical_amount, 2))
        seen_keys.add(key)
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
    # Drop stale detections (e.g. two same-week Pressbyrån purchases)
    for r in existing_rows:
        key = (r["normalized_merchant"], r["cadence"], round(r["typical_amount"], 2))
        if key not in seen_keys:
            conn.execute("DELETE FROM recurring_groups WHERE id = ?", (r["id"],))


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
    transfer_review: bool | None = None,
    transfers_only: bool | None = None,
    category: str | None = None,
    search: str | None = None,
    tag: str | None = None,
    month: str | None = None,
    sort: str = "date_desc",
    limit: int = 500,
    offset: int = 0,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, MAX_TRANSACTION_LIMIT))
    offset = max(0, offset)
    order_by = _SORT_OPTIONS.get(sort, _SORT_OPTIONS["date_desc"])
    clauses: list[str] = []
    params: list[Any] = []
    if needs_review is True:
        clauses.append("t.needs_review = 1")
    if needs_review is False:
        clauses.append("t.needs_review = 0")
    if income_review is True:
        clauses.append("t.amount > 0")
        clauses.append("t.category NOT IN (?, ?)")
        params.extend([INCOME_CAT, TRANSFER_CAT])
    if transfer_review is True:
        clauses.append("t.category = ?")
        params.append(TRANSFER_CAT)
        clauses.append("t.transfer_kind IS NULL")
    if transfers_only is True and transfer_review is not True:
        clauses.append("t.category = ?")
        params.append(TRANSFER_CAT)
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
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        out = rows_to_dicts(rows)
        for row in out:
            raw = row.pop("tags_csv", None) or ""
            row["tags"] = [t.strip() for t in raw.split(",") if t.strip()]
            row["group_key"] = group_key(row.get("raw_description") or "")
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


def breakdown(
    kind: str = "spent",
    *,
    month: str | None = None,
    months: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = [TRANSFER_CAT]
    if kind == "income":
        clauses.append("amount > 0 AND category NOT IN (?, 'Unclear')")
        order = "total DESC"
    else:
        clauses.append("amount < 0 AND category NOT IN (?, 'Unclear')")
        order = "total ASC"

    if month:
        # YYYY-MM
        clauses.append("substr(tx_date, 1, 7) = ?")
        params.append(month)
    elif months is not None:
        clauses.append("tx_date >= ?")
        params.append(_date_cutoff(max(1, min(int(months), 36))))

    where = " AND ".join(clauses)
    sql = f"""
        SELECT category, ROUND(SUM(amount), 2) AS total, COUNT(*) AS tx_count
        FROM transactions
        WHERE {where}
        GROUP BY category
        ORDER BY {order}
    """
    with get_db() as conn:
        return rows_to_dicts(conn.execute(sql, params).fetchall())


def transfer_summary() -> dict[str, Any]:
    with get_db() as conn:
        internal = conn.execute(
            """
            SELECT COUNT(*) AS c, COALESCE(SUM(ABS(amount)), 0) AS v
            FROM transactions
            WHERE category = ? AND transfer_kind = 'internal'
            """,
            (TRANSFER_CAT,),
        ).fetchone()
        pending = conn.execute(
            """
            SELECT COUNT(*) AS c, COALESCE(SUM(ABS(amount)), 0) AS v
            FROM transactions
            WHERE category = ? AND transfer_kind IS NULL
            """,
            (TRANSFER_CAT,),
        ).fetchone()
    return {
        "internal_volume": round(float(internal["v"]), 2),
        "internal_count": int(internal["c"]),
        "pending_count": int(pending["c"]),
        "pending_volume": round(float(pending["v"]), 2),
    }


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
        "transfer_summary": transfer_summary(),
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
            key = clean_match_text(match_text or merchant_key(row["raw_description"]))
            if not key:
                key = merchant_key(row["raw_description"])
            conn.execute(
                """
                INSERT INTO category_rules (match_text, category, enabled, created_at)
                VALUES (?, ?, 1, ?)
                ON CONFLICT(match_text) DO UPDATE SET category = excluded.category, enabled = 1
                """,
                (key, category, now_iso()),
            )
            source = "learned"
            apply_rule_to_existing(conn, key, category)
        conn.execute(
            """
            UPDATE transactions
            SET category = ?, category_source = ?, confidence = 1.0, needs_review = 0,
                transfer_kind = ?
            WHERE id = ?
            """,
            (
                category,
                source,
                resolve_transfer_kind(category, row["raw_description"]),
                tx_id,
            ),
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
            SELECT COALESCE(SUM(ABS(amount)), 0) AS s FROM transactions
            WHERE category = ? AND transfer_kind = 'internal'
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


def bulk_update_category(
    ids: list[int],
    category: str,
    remember: bool,
    match_text: str | None = None,
) -> int:
    category = ensure_category(category)
    if not ids:
        return 0
    if remember:
        with get_db() as conn:
            key = clean_match_text(match_text) if match_text else ""
            if not key:
                row = conn.execute(
                    "SELECT raw_description FROM transactions WHERE id = ?", (ids[0],)
                ).fetchone()
                if row:
                    key = clean_match_text(merchant_key(row["raw_description"]))
            if key:
                conn.execute(
                    """
                    INSERT INTO category_rules (match_text, category, enabled, created_at)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(match_text) DO UPDATE SET category = excluded.category, enabled = 1
                    """,
                    (key, category, now_iso()),
                )
                apply_rule_to_existing(conn, key, category)
            updated = 0
            for tx_id in ids:
                row = conn.execute(
                    "SELECT raw_description FROM transactions WHERE id = ?", (tx_id,)
                ).fetchone()
                tk = resolve_transfer_kind(category, row["raw_description"]) if row else None
                cur = conn.execute(
                    """
                    UPDATE transactions
                    SET category = ?, category_source = 'learned', confidence = 1.0, needs_review = 0,
                        transfer_kind = ?
                    WHERE id = ?
                    """,
                    (category, tk, tx_id),
                )
                updated += cur.rowcount
            return updated
    updated = 0
    for tx_id in ids:
        try:
            update_transaction_category(tx_id, category, remember=False)
            updated += 1
        except KeyError:
            continue
    return updated


def classify_transfer(
    transaction_ids: list[int],
    kind: str,
    *,
    category: str | None = None,
    remember: bool = False,
    match_text: str | None = None,
) -> int:
    """Classify bank transfers as internal (excluded), income, or expense."""
    kind = kind.strip().lower()
    if kind not in ("internal", "income", "expense"):
        raise ValueError("invalid transfer kind")
    if kind == "expense" and not category:
        raise ValueError("category required for expense")
    if not transaction_ids:
        return 0

    if kind == "internal":
        target_category = TRANSFER_CAT
        target_kind: str | None = "internal"
    elif kind == "income":
        target_category = INCOME_CAT
        target_kind = None
    else:
        target_category = ensure_category(category or "Other")
        target_kind = None

    updated = 0
    with get_db() as conn:
        key = ""
        if remember:
            sample = conn.execute(
                "SELECT raw_description FROM transactions WHERE id = ?", (transaction_ids[0],)
            ).fetchone()
            if sample:
                key = clean_match_text(match_text or merchant_key(sample["raw_description"]))
                if not key:
                    key = merchant_key(sample["raw_description"])
            if key:
                conn.execute(
                    """
                    INSERT INTO category_rules (match_text, category, enabled, created_at)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT(match_text) DO UPDATE SET category = excluded.category, enabled = 1
                    """,
                    (key, target_category, now_iso()),
                )
        source = "learned" if remember and key else "manual_once"
        for tx_id in transaction_ids:
            if not conn.execute("SELECT id FROM transactions WHERE id = ?", (tx_id,)).fetchone():
                continue
            conn.execute(
                """
                UPDATE transactions
                SET category = ?, category_source = ?, confidence = 1.0, needs_review = 0,
                    transfer_kind = ?
                WHERE id = ?
                """,
                (target_category, source, target_kind, tx_id),
            )
            updated += 1
        if remember and key:
            if kind == "internal":
                rows = conn.execute(
                    "SELECT id, raw_description FROM transactions WHERE category_source != 'manual_once'"
                ).fetchall()
                for row in rows:
                    if phrase_matches(key, row["raw_description"]):
                        conn.execute(
                            """
                            UPDATE transactions
                            SET category = ?, category_source = 'learned', confidence = 0.95,
                                needs_review = 0, transfer_kind = 'internal'
                            WHERE id = ?
                            """,
                            (TRANSFER_CAT, row["id"]),
                        )
            else:
                apply_rule_to_existing(conn, key, target_category)
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


def update_rule(
    rule_id: int,
    *,
    category: str | None = None,
    enabled: bool | None = None,
    match_text: str | None = None,
) -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM category_rules WHERE id = ?", (rule_id,)).fetchone()
        if not row:
            raise KeyError("not found")
        cat = ensure_category(category) if category else row["category"]
        en = row["enabled"] if enabled is None else (1 if enabled else 0)
        key = clean_match_text(match_text) if match_text is not None else row["match_text"]
        if not key:
            raise ValueError("match_text cannot be empty")
        if key != row["match_text"]:
            conflict = conn.execute(
                "SELECT id FROM category_rules WHERE match_text = ? AND id != ?",
                (key, rule_id),
            ).fetchone()
            if conflict:
                raise ValueError("A rule with that match text already exists")
        conn.execute(
            "UPDATE category_rules SET match_text = ?, category = ?, enabled = ? WHERE id = ?",
            (key, cat, en, rule_id),
        )
        if en:
            apply_rule_to_existing(conn, key, cat)
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


_CADENCE_YEARLY: dict[str, float] = {
    "weekly": 52,
    "monthly": 12,
    "quarterly": 4,
    "yearly": 1,
}


def price_alerts() -> list[dict[str, Any]]:
    with get_db() as conn:
        _detect_price_changes(conn)
        rows = rows_to_dicts(
            conn.execute(
                """
                SELECT pe.*,
                       rg.name,
                       rg.cadence,
                       rg.typical_amount,
                       rg.id AS recurring_group_id
                FROM recurring_price_events pe
                INNER JOIN recurring_groups rg
                  ON rg.normalized_merchant = pe.normalized_merchant
                 AND rg.decision NOT IN ('ignore')
                WHERE pe.acknowledged = 0
                ORDER BY pe.detected_at DESC
                LIMIT 20
                """
            ).fetchall()
        )
    for row in rows:
        old = float(row["old_amount"])
        new = float(row["new_amount"])
        row["pct_change"] = round((new - old) / old * 100, 1) if old > 0 else 0
        factor = _CADENCE_YEARLY.get(str(row.get("cadence") or "monthly"), 12)
        row["yearly_delta"] = round((new - old) * factor, 2)
    return rows


def acknowledge_price_event(event_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE recurring_price_events SET acknowledged = 1 WHERE id = ?",
            (event_id,),
        )


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
