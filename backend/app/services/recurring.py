from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median


@dataclass
class RecurringCandidate:
    name: str
    normalized_merchant: str
    cadence: str
    typical_amount: float
    yearly_cost: float
    occurrence_count: int
    last_seen: str


def _days_between(a: str, b: str) -> int:
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)


def _infer_cadence(dates: list[str]) -> str:
    if len(dates) < 2:
        return "irregular"
    ordered = sorted(dates)
    gaps = [_days_between(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)]
    g = median(gaps)
    if 5 <= g <= 9:
        return "weekly"
    if 25 <= g <= 35:
        return "monthly"
    if 80 <= g <= 100:
        return "quarterly"
    if 340 <= g <= 390:
        return "yearly"
    return "irregular"


def _yearly_from(amount: float, cadence: str, count: int, span_days: int) -> float:
    abs_amt = abs(amount)
    if cadence == "weekly":
        return abs_amt * 52
    if cadence == "monthly":
        return abs_amt * 12
    if cadence == "quarterly":
        return abs_amt * 4
    if cadence == "yearly":
        return abs_amt
    # irregular: extrapolate from window
    if span_days <= 0:
        return abs_amt * count
    return abs_amt * count * (365.0 / span_days)


def detect_recurring(
    transactions: list[dict],
    min_occurrences: int = 2,
) -> list[RecurringCandidate]:
    """Cluster expense transactions by merchant + similar amount."""
    expenses = [t for t in transactions if float(t["amount"]) < 0]
    buckets: dict[tuple[str, int], list[dict]] = defaultdict(list)

    for t in expenses:
        merchant = t["normalized_merchant"]
        # bucket amount to nearest 5 kr for clustering
        amt_bucket = int(round(abs(float(t["amount"])) / 5.0) * 5)
        buckets[(merchant, amt_bucket)].append(t)

    out: list[RecurringCandidate] = []
    for (merchant, _), rows in buckets.items():
        if len(rows) < min_occurrences:
            continue
        dates = [r["tx_date"] for r in rows]
        amounts = [abs(float(r["amount"])) for r in rows]
        typical = float(median(amounts))
        # relative tolerance: amounts should be similar
        if typical == 0:
            continue
        if max(amounts) / max(typical, 0.01) > 1.35:
            continue
        cadence = _infer_cadence(dates)
        span = _days_between(min(dates), max(dates)) or 1
        yearly = _yearly_from(typical, cadence, len(rows), span)
        # Prefer human name from raw description of latest
        latest = max(rows, key=lambda r: r["tx_date"])
        name = _pretty_name(latest.get("raw_description") or merchant)
        out.append(
            RecurringCandidate(
                name=name,
                normalized_merchant=merchant,
                cadence=cadence,
                typical_amount=round(typical, 2),
                yearly_cost=round(yearly, 2),
                occurrence_count=len(rows),
                last_seen=max(dates),
            )
        )

    out.sort(key=lambda c: c.yearly_cost, reverse=True)
    return out


def _pretty_name(raw: str) -> str:
    s = " ".join((raw or "").split())
    if len(s) > 48:
        s = s[:45] + "…"
    return s.title() if s.isupper() else s
