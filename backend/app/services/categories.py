"""User-managed spending categories (slug + display name)."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..db import CATEGORIES, get_db, rows_to_dicts
from .categorize import categorize

_UNCLEAR_THRESHOLD = 0.55

# All built-in categories are protected: rename/create custom OK, delete/merge-away not.
SYSTEM_SLUGS = frozenset(CATEGORIES)

# Swedish default display names used when seeding the categories table.
DEFAULT_NAMES_SV: dict[str, str] = {
    "Housing": "Boende",
    "Groceries": "Mat",
    "Transport": "Transport",
    "Restaurants": "Restaurang",
    "Subscriptions": "Abonnemang",
    "Shopping": "Shopping",
    "Health": "Hälsa",
    "Income": "Inkomst",
    "Transfers": "Överföringar",
    "Fees": "Avgifter",
    "Other": "Övrigt",
    "Unclear": "Oklart",
}

_slug_cache: frozenset[str] | None = None


def _invalidate_cache() -> None:
    global _slug_cache
    _slug_cache = None


def all_slugs(conn=None) -> frozenset[str]:
    global _slug_cache
    if _slug_cache is not None:
        return _slug_cache
    if conn is not None:
        rows = conn.execute("SELECT slug FROM categories").fetchall()
        _slug_cache = frozenset(r["slug"] for r in rows)
        return _slug_cache
    with get_db() as c:
        rows = c.execute("SELECT slug FROM categories").fetchall()
        _slug_cache = frozenset(r["slug"] for r in rows)
        return _slug_cache


def ensure_category_slug(name: str) -> str:
    """Return a valid category slug, or Other if unknown."""
    slug = (name or "").strip()
    if slug in all_slugs():
        return slug
    return "Other"


def seed_categories(conn) -> None:
    """Ensure the standard category set exists (restore if deleted).

    Custom categories and renames are preserved. Missing builtins are
    re-inserted with Swedish default names; existing builtins are marked
    system so they cannot be deleted again.
    """
    for i, slug in enumerate(CATEGORIES):
        name = DEFAULT_NAMES_SV.get(slug, slug)
        existing = conn.execute(
            "SELECT slug, name FROM categories WHERE slug = ?", (slug,)
        ).fetchone()
        if existing is None:
            conn.execute(
                """
                INSERT INTO categories (slug, name, is_system, sort_order)
                VALUES (?, ?, 1, ?)
                """,
                (slug, name, i),
            )
        else:
            conn.execute(
                """
                UPDATE categories
                SET is_system = 1, sort_order = ?
                WHERE slug = ?
                """,
                (i, slug),
            )
    _invalidate_cache()


def list_categories() -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.slug, c.name, c.is_system, c.sort_order,
                   (SELECT COUNT(*) FROM transactions t WHERE t.category = c.slug) AS tx_count
            FROM categories c
            ORDER BY c.sort_order, c.name
            """
        ).fetchall()
        return rows_to_dicts(rows)


def create_category(name: str) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("category name required")
    slug = _unique_slug(name)
    with get_db() as conn:
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), -1) AS m FROM categories").fetchone()["m"]
        conn.execute(
            """
            INSERT INTO categories (slug, name, is_system, sort_order)
            VALUES (?, ?, 0, ?)
            """,
            (slug, name, int(max_order) + 1),
        )
        row = conn.execute(
            "SELECT slug, name, is_system, sort_order FROM categories WHERE slug = ?", (slug,)
        ).fetchone()
    _invalidate_cache()
    out = dict(row)
    out["tx_count"] = 0
    return out


def rename_category(slug: str, name: str) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise ValueError("category name required")
    with get_db() as conn:
        row = conn.execute("SELECT slug FROM categories WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise KeyError("category not found")
        conn.execute("UPDATE categories SET name = ? WHERE slug = ?", (name, slug))
        return _category_row(conn, slug)


def _learned_rules_excluding(conn, slug: str) -> list[tuple[str, str]]:
    return [
        (r["match_text"], r["category"])
        for r in conn.execute(
            """
            SELECT match_text, category FROM category_rules
            WHERE enabled = 1 AND category != ?
            ORDER BY length(match_text) DESC
            """,
            (slug,),
        ).fetchall()
    ]


def _estimate_delete_outcomes(
    txs: list[Any],
    learned: list[tuple[str, str]],
    removed_slug: str,
) -> tuple[int, int]:
    recategorized = 0
    unclear = 0
    for tx in txs:
        if tx["category_source"] == "manual_once":
            unclear += 1
            continue
        result = categorize(tx["raw_description"], float(tx["amount"]), learned)
        if (
            result.category == removed_slug
            or result.needs_review
            or result.confidence < _UNCLEAR_THRESHOLD
        ):
            unclear += 1
        else:
            recategorized += 1
    return recategorized, unclear


def delete_preview(slug: str) -> dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT slug FROM categories WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise KeyError("category not found")
        txs = conn.execute(
            """
            SELECT id, raw_description, amount, category_source
            FROM transactions WHERE category = ?
            """,
            (slug,),
        ).fetchall()
        learned = _learned_rules_excluding(conn, slug)
        recategorized, unclear = _estimate_delete_outcomes(txs, learned, slug)
        rules_count = conn.execute(
            "SELECT COUNT(*) AS c FROM category_rules WHERE category = ?", (slug,)
        ).fetchone()["c"]
        budgets_count = conn.execute(
            "SELECT COUNT(*) AS c FROM budgets WHERE category = ?", (slug,)
        ).fetchone()["c"]
    return {
        "slug": slug,
        "tx_count": len(txs),
        "estimated_recategorizable": recategorized,
        "estimated_unclear": unclear,
        "rules_count": int(rules_count),
        "budgets_count": int(budgets_count),
        "is_system": slug in SYSTEM_SLUGS,
    }


def delete_category(slug: str) -> dict[str, Any]:
    if slug in SYSTEM_SLUGS:
        raise ValueError("system categories cannot be deleted")
    with get_db() as conn:
        row = conn.execute("SELECT slug FROM categories WHERE slug = ?", (slug,)).fetchone()
        if not row:
            raise KeyError("category not found")

        txs = conn.execute(
            "SELECT id, raw_description, amount, category_source FROM transactions WHERE category = ?",
            (slug,),
        ).fetchall()
        learned = _learned_rules_excluding(conn, slug)
        conn.execute("DELETE FROM category_rules WHERE category = ?", (slug,))
        conn.execute("DELETE FROM budgets WHERE category = ?", (slug,))
        conn.execute("DELETE FROM categories WHERE slug = ?", (slug,))
        _invalidate_cache()

        recategorized = 0
        unclear = 0
        for tx in txs:
            if tx["category_source"] == "manual_once":
                conn.execute(
                    """
                    UPDATE transactions
                    SET category = 'Unclear', category_source = 'unclear',
                        confidence = 0.4, needs_review = 1
                    WHERE id = ?
                    """,
                    (tx["id"],),
                )
                unclear += 1
                continue
            result = categorize(tx["raw_description"], float(tx["amount"]), learned)
            if (
                result.category == slug
                or result.needs_review
                or result.confidence < _UNCLEAR_THRESHOLD
            ):
                conn.execute(
                    """
                    UPDATE transactions
                    SET category = 'Unclear', category_source = 'unclear',
                        confidence = ?, needs_review = 1
                    WHERE id = ?
                    """,
                    (result.confidence, tx["id"]),
                )
                unclear += 1
            else:
                conn.execute(
                    """
                    UPDATE transactions
                    SET category = ?, category_source = ?, confidence = ?, needs_review = 0
                    WHERE id = ?
                    """,
                    (result.category, result.source, result.confidence, tx["id"]),
                )
                recategorized += 1

    return {
        "status": "ok",
        "removed_slug": slug,
        "transactions_recategorized": recategorized,
        "transactions_unclear": unclear,
    }


def merge_categories(source_slug: str, target_slug: str) -> dict[str, Any]:
    if source_slug == target_slug:
        raise ValueError("cannot merge category into itself")
    if source_slug in SYSTEM_SLUGS:
        raise ValueError("system categories cannot be merged")
    with get_db() as conn:
        source = conn.execute(
            "SELECT slug FROM categories WHERE slug = ?", (source_slug,)
        ).fetchone()
        target = conn.execute(
            "SELECT slug FROM categories WHERE slug = ?", (target_slug,)
        ).fetchone()
        if not source or not target:
            raise KeyError("category not found")

        tx_count = conn.execute(
            "SELECT COUNT(*) AS c FROM transactions WHERE category = ?", (source_slug,)
        ).fetchone()["c"]
        rules_count = conn.execute(
            "SELECT COUNT(*) AS c FROM category_rules WHERE category = ?", (source_slug,)
        ).fetchone()["c"]
        source_budget = conn.execute(
            "SELECT 1 FROM budgets WHERE category = ?", (source_slug,)
        ).fetchone()
        target_budget = conn.execute(
            "SELECT 1 FROM budgets WHERE category = ?", (target_slug,)
        ).fetchone()
        budget_moved = 0
        if source_budget and not target_budget:
            conn.execute(
                "UPDATE budgets SET category = ? WHERE category = ?",
                (target_slug, source_slug),
            )
            budget_moved = 1
        elif source_budget:
            conn.execute("DELETE FROM budgets WHERE category = ?", (source_slug,))

        conn.execute(
            "UPDATE transactions SET category = ? WHERE category = ?",
            (target_slug, source_slug),
        )
        conn.execute(
            "UPDATE category_rules SET category = ? WHERE category = ?",
            (target_slug, source_slug),
        )
        conn.execute("DELETE FROM categories WHERE slug = ?", (source_slug,))
    _invalidate_cache()
    return {
        "status": "ok",
        "merged_slug": source_slug,
        "target_slug": target_slug,
        "transactions_moved": int(tx_count),
        "rules_moved": int(rules_count),
        "budget_moved": budget_moved,
    }


def _category_row(conn, slug: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT c.slug, c.name, c.is_system, c.sort_order,
               (SELECT COUNT(*) FROM transactions t WHERE t.category = c.slug) AS tx_count
        FROM categories c WHERE c.slug = ?
        """,
        (slug,),
    ).fetchone()
    return dict(row)


def _unique_slug(name: str) -> str:
    base = _slugify(name)
    if not base:
        base = "category"
    slug = base[:48]
    with get_db() as conn:
        if not conn.execute("SELECT 1 FROM categories WHERE slug = ?", (slug,)).fetchone():
            return slug
        for i in range(2, 100):
            candidate = f"{base[:44]}_{i}"
            if not conn.execute("SELECT 1 FROM categories WHERE slug = ?", (candidate,)).fetchone():
                return candidate
    raise ValueError("could not allocate unique category slug")


def _slugify(name: str) -> str:
    s = unicodedata.normalize("NFKC", name).strip()
    s = s.replace(" ", "_")
    s = re.sub(r"[^\w]", "", s, flags=re.UNICODE)
    if s and s[0].isdigit():
        s = f"c_{s}"
    return s[:48] if s else "category"
