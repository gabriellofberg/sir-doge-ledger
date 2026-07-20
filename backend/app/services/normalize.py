from __future__ import annotations

import re
import unicodedata

_NOISE = re.compile(
    r"\b(AB|AKTIEBOLAG|KORTK[ÖO]P|CARD\s*PURCHASE|BETALNING|AUTOGIRO|"
    r"KLARNA|PAYPAL|SUMUP|IZETTLE|VISA|MASTERCARD|DEBIT|CREDIT|BG)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^A-Z0-9ÅÄÖ\s]+")
_SPACES = re.compile(r"\s+")
# Bank date stamps (YYMMDD / YYYYMMDD) and long pure-numeric refs (BG etc.)
_REF_TOKEN = re.compile(r"^(\d{6}|\d{8}|\d{4,})$")


def _fold_ascii(token: str) -> str:
    """Fold Swedish letters so VÄSTTRAFIK matches VASTTRAFIK."""
    return (
        token.replace("Å", "A")
        .replace("Ä", "A")
        .replace("Ö", "O")
        .replace("É", "E")
        .replace("Ü", "U")
    )


def normalize_merchant(text: str) -> str:
    raw = unicodedata.normalize("NFKC", text or "").upper().strip()
    raw = _NOISE.sub(" ", raw)
    raw = _NON_ALNUM.sub(" ", raw)
    raw = _SPACES.sub(" ", raw).strip()
    return raw or "UNKNOWN"


def significant_tokens(text: str) -> list[str]:
    """Merchant tokens without leading bank dates / numeric references."""
    return [p for p in normalize_merchant(text).split() if not _REF_TOKEN.match(p)]


def merchant_key(text: str, max_tokens: int = 4) -> str:
    """Shorter key used for learning rules and clustering."""
    parts = significant_tokens(text)
    if not parts:
        # Fall back so we still learn something if description was only dates/noise
        parts = normalize_merchant(text).split()
    return " ".join(parts[:max_tokens]) if parts else "UNKNOWN"


def group_key(text: str) -> str:
    """Coarse review-group key: first significant merchant token (SJ, VÄSTTRAFIK, SWISH…)."""
    parts = significant_tokens(text)
    if not parts:
        parts = normalize_merchant(text).split()
    return parts[0] if parts else "UNKNOWN"


def clean_match_text(text: str) -> str:
    """Normalize a rule match string the same way as learned merchant keys."""
    cleaned = merchant_key(text, max_tokens=8)
    return cleaned if cleaned != "UNKNOWN" else (text or "").upper().strip()


def phrase_matches(match_text: str, description: str) -> bool:
    """True if match_text appears as a contiguous token sequence in the description.

    So \"SJ\" matches \"KORTKÖP 260715 SJ GBG\" but not a random substring inside
    another word. Multi-word phrases like \"TOO GOOD TO GO\" match as a whole.
    Swedish letters are folded so VÄSTTRAFIK matches VASTTRAFIK.
    """
    needle = [_fold_ascii(t) for t in clean_match_text(match_text).split()]
    if not needle:
        return False
    hay = significant_tokens(description)
    if not hay:
        hay = normalize_merchant(description).split()
    hay_folded = [_fold_ascii(t) for t in hay]
    n = len(needle)
    if n > len(hay_folded):
        hay_folded = [_fold_ascii(t) for t in normalize_merchant(description).split()]
    for i in range(len(hay_folded) - n + 1):
        if hay_folded[i : i + n] == needle:
            return True
    return False
