from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median


# Exclude one-off noise and money movement that is not a subscription.
_EXCLUDED_CATEGORIES = {"Transfers", "Income", "Unclear"}

# Need real repetition across time — not two Pressbyrån coffees in one week.
_MIN_DISTINCT_DATES = 3
_MIN_SPAN_DAYS = 60


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


def _unique_sorted_dates(dates: list[str]) -> list[str]:
    return sorted(set(dates))


def _month_key(d: str) -> str:
    return d[:7]  # YYYY-MM


def _day_of_month(d: str) -> int:
    return date.fromisoformat(d).day


def _infer_cadence(dates: list[str]) -> str | None:
    """Return a known cadence, or None if the pattern is not subscription-like."""
    ordered = _unique_sorted_dates(dates)
    if len(ordered) < _MIN_DISTINCT_DATES:
        return None

    gaps = [_days_between(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)]
    # Ignore same-day / next-day doubles when inferring rhythm
    meaningful_gaps = [g for g in gaps if g >= 5]
    if len(meaningful_gaps) < 2:
        # Fall back to calendar-month pattern (same ~day three months in a row)
        if _looks_like_monthly_bill(ordered):
            return "monthly"
        return None

    g = median(meaningful_gaps)
    if 5 <= g <= 9:
        return "weekly"
    if 25 <= g <= 40:
        return "monthly"
    if 80 <= g <= 100:
        return "quarterly"
    if 340 <= g <= 390:
        return "yearly"
    if _looks_like_monthly_bill(ordered):
        return "monthly"
    return None


def _looks_like_monthly_bill(ordered_dates: list[str]) -> bool:
    """True if the same (approx) day-of-month appears in ≥3 distinct months."""
    by_month: dict[str, list[int]] = defaultdict(list)
    for d in ordered_dates:
        by_month[_month_key(d)].append(_day_of_month(d))
    if len(by_month) < 3:
        return False
    # Pick the dominant day-of-month across months (tolerance ±3 days)
    all_days = [day for days in by_month.values() for day in days]
    anchor = int(median(all_days))
    months_hit = 0
    for days in by_month.values():
        if any(abs(day - anchor) <= 3 for day in days):
            months_hit += 1
    return months_hit >= 3


def _yearly_from(amount: float, cadence: str) -> float:
    abs_amt = abs(amount)
    if cadence == "weekly":
        return abs_amt * 52
    if cadence == "monthly":
        return abs_amt * 12
    if cadence == "quarterly":
        return abs_amt * 4
    if cadence == "yearly":
        return abs_amt
    return abs_amt * 12


def detect_recurring(
    transactions: list[dict],
    min_occurrences: int = _MIN_DISTINCT_DATES,
) -> list[RecurringCandidate]:
    """Cluster expense transactions by merchant + similar amount.

    Only returns candidates with a clear weekly/monthly/quarterly/yearly rhythm
    across at least three distinct dates spanning ~two months (or the same
    day-of-month across three calendar months).
    """
    expenses = [
        t
        for t in transactions
        if float(t["amount"]) < 0 and (t.get("category") or "") not in _EXCLUDED_CATEGORIES
    ]
    buckets: dict[tuple[str, int], list[dict]] = defaultdict(list)

    for t in expenses:
        merchant = t["normalized_merchant"]
        # bucket amount to nearest 5 kr for clustering
        amt_bucket = int(round(abs(float(t["amount"])) / 5.0) * 5)
        buckets[(merchant, amt_bucket)].append(t)

    out: list[RecurringCandidate] = []
    for (merchant, _), rows in buckets.items():
        dates = [r["tx_date"] for r in rows]
        unique_dates = _unique_sorted_dates(dates)
        if len(unique_dates) < min_occurrences:
            continue

        span = _days_between(unique_dates[0], unique_dates[-1])
        cadence = _infer_cadence(unique_dates)
        if cadence is None:
            continue
        # Require enough calendar span unless we already matched a monthly bill pattern
        if span < _MIN_SPAN_DAYS and not _looks_like_monthly_bill(unique_dates):
            continue

        amounts = [abs(float(r["amount"])) for r in rows]
        typical = float(median(amounts))
        if typical == 0:
            continue
        if max(amounts) / max(typical, 0.01) > 1.35:
            continue

        yearly = _yearly_from(typical, cadence)
        latest = max(rows, key=lambda r: r["tx_date"])
        name = _pretty_name(latest.get("raw_description") or merchant)
        out.append(
            RecurringCandidate(
                name=name,
                normalized_merchant=merchant,
                cadence=cadence,
                typical_amount=round(typical, 2),
                yearly_cost=round(yearly, 2),
                occurrence_count=len(unique_dates),
                last_seen=unique_dates[-1],
            )
        )

    out.sort(key=lambda c: c.yearly_cost, reverse=True)
    return out


def _pretty_name(raw: str) -> str:
    s = " ".join((raw or "").split())
    if len(s) > 48:
        s = s[:45] + "…"
    return s.title() if s.isupper() else s
