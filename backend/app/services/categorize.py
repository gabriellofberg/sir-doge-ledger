from __future__ import annotations

import re
from dataclasses import dataclass

from ..db import CATEGORIES
from .normalize import merchant_key, normalize_merchant

# (category, keywords) — first strong match wins among builtins; learned rules override.
_BUILTIN: list[tuple[str, list[str]]] = [
    (
        "Housing",
        [
            "HYRA",
            "RENT",
            "BOSTAD",
            "BRF",
            "FASTIGHET",
            "HEMFORSAKR",
            "HEMFÖRSÄKR",
            "ELNÄT",
            "VATTENFALL",
            "EON",
            "FORTUM",
            "STOCKHOLM EXERGI",
            "VA SYD",
            "SOPHÄMT",
        ],
    ),
    (
        "Groceries",
        [
            "ICA",
            "COOP",
            "WILLYS",
            "LIDL",
            "HEMKÖP",
            "HEMKOP",
            "CITY GROSS",
            "MATHEM",
            "FOODORA MARKET",
            "AXFOOD",
        ],
    ),
    (
        "Transport",
        [
            " SL",
            "SL ",
            "SLKORT",
            "SL ACCESS",
            "UL ",
            "SKANETRAFIKEN",
            "SKÅNETRAFIKEN",
            "UBER",
            "BOLT",
            "TAXI",
            "CIRCLE K",
            "PREEM",
            "OKQ8",
            "SHELL",
            "INGO",
            "SJ AB",
            "MTRX",
            "FLIXBUS",
            "PARKERING",
            "EASYPARK",
        ],
    ),
    (
        "Restaurants",
        [
            "RESTAURANT",
            "RESTAURANG",
            "CAFE",
            "CAFÉ",
            "COFFEE",
            "ESPRESSO HOUSE",
            "STARBUCKS",
            "MAX BURGER",
            "MCDONALD",
            "BURGER KING",
            "FOODORA",
            "UBER EATS",
            "WOLT",
            "PIZZA",
            "SUSHI",
        ],
    ),
    (
        "Subscriptions",
        [
            "SPOTIFY",
            "NETFLIX",
            "DISNEY",
            "HBO",
            "VIAPLAY",
            "YOUTUBE",
            "APPLE.COM/BILL",
            "APPLE COM BILL",
            "GOOGLE STORAGE",
            "ICLOUD",
            "MICROSOFT",
            "ADOBE",
            "DROPBOX",
            "GITHUB",
            "OPENAI",
            "CHATGPT",
            "CURSOR",
            "NORDVPN",
            "EXPRESSVPN",
            "STORYTEL",
            "BOOKBEAT",
            "AUDIBLE",
            "PATREON",
            "TWITCH",
        ],
    ),
    (
        "Shopping",
        [
            "AMAZON",
            "ZALANDO",
            "HM ",
            "H&M",
            "IKEA",
            "ELGIGANTEN",
            "MEDIA MARKT",
            "WEBHALLEN",
            "CDON",
            "APOTEA",
            "APOTEK",
            "CLAS OHLSON",
            "BILTEMA",
            "JYSK",
        ],
    ),
    (
        "Health",
        [
            "APOTEK",
            "VARDCENTRAL",
            "VÅRDCENTRAL",
            "FOLKTAND",
            "DENTAL",
            "GYM",
            "FITNESS",
            "SATSA",
            "NORDIC WELLNESS",
            "FYSIOTER",
        ],
    ),
    (
        "Income",
        [
            "LÖN",
            "LON ",
            "SALARY",
            "UTBETALNING",
            "SKATTEVERKET",
            "ÅTERBETALNING",
            "ATERBETALNING",
        ],
    ),
    (
        "Transfers",
        [
            "ÖVERFÖRING",
            "OVERFORING",
            "TRANSFER",
            "EGNA KONTON",
            "SPARA",
            "AVANZA",
            "NORDNET",
            "SWISH TILL",
        ],
    ),
    (
        "Fees",
        [
            "AVGIFT",
            "FEE",
            "ÅRSAVGIFT",
            "ARSAVGIFT",
            "KORTAVGIFT",
            "RÄNTA",
            "RANTA",
        ],
    ),
]

_HIGH = 0.9
_MED = 0.65
_LOW = 0.4
_UNCLEAR_THRESHOLD = 0.55


@dataclass
class CategoryResult:
    category: str
    source: str  # learned | auto | unclear
    confidence: float
    needs_review: bool


def categorize(
    description: str,
    amount: float,
    learned_rules: list[tuple[str, str]],
) -> CategoryResult:
    """Return category attempt. learned_rules: list of (match_text, category)."""
    norm = normalize_merchant(description)
    key = merchant_key(description)

    for match_text, category in learned_rules:
        mt = match_text.upper().strip()
        if mt and (mt in norm or norm.startswith(mt) or key == mt):
            return CategoryResult(category, "learned", _HIGH, False)

    if amount > 0:
        # Income heuristic when description weak
        for cat, words in _BUILTIN:
            if cat != "Income":
                continue
            for w in words:
                if w.strip() in norm:
                    return CategoryResult("Income", "auto", _HIGH, False)

    best: CategoryResult | None = None
    for category, words in _BUILTIN:
        for w in words:
            token = w.strip().upper()
            if not token:
                continue
            if token in norm:
                conf = _HIGH if len(token) >= 5 else _MED
                candidate = CategoryResult(category, "auto", conf, conf < _UNCLEAR_THRESHOLD)
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

    if best is None:
        return CategoryResult("Unclear", "unclear", _LOW, True)

    if best.confidence < _UNCLEAR_THRESHOLD:
        return CategoryResult(
            best.category if best.category != "Unclear" else "Unclear",
            "unclear",
            best.confidence,
            True,
        )

    # Clear keyword / amount heuristics: trust them; only Unclear goes to review queue
    return CategoryResult(best.category, "auto", best.confidence, False)


def ensure_category(name: str) -> str:
    if name in CATEGORIES:
        return name
    return "Other"
