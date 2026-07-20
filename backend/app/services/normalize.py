from __future__ import annotations

import re
import unicodedata

_NOISE = re.compile(
    r"\b(AB|AKTIEBOLAG|KORTK[ÖO]P|CARD\s*PURCHASE|BETALNING|AUTOGIRO|SWISH|"
    r"KLARNA|PAYPAL|SUMUP|IZETTLE|VISA|MASTERCARD|DEBIT|CREDIT)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^A-Z0-9ÅÄÖ\s]+")
_SPACES = re.compile(r"\s+")


def normalize_merchant(text: str) -> str:
    raw = unicodedata.normalize("NFKC", text or "").upper().strip()
    raw = _NOISE.sub(" ", raw)
    raw = _NON_ALNUM.sub(" ", raw)
    raw = _SPACES.sub(" ", raw).strip()
    return raw or "UNKNOWN"


def merchant_key(text: str, max_tokens: int = 4) -> str:
    """Shorter key used for learning rules and clustering."""
    parts = normalize_merchant(text).split()
    return " ".join(parts[:max_tokens]) if parts else "UNKNOWN"
