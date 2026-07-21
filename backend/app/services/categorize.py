from __future__ import annotations

from dataclasses import dataclass

from .normalize import phrase_matches
from .settings import get_setting

_DEFAULT_FOODORA_THRESHOLD = 350.0

# (category, keywords) — first strong match wins among builtins; learned rules override.
# Keywords are matched as whole token sequences (not raw substrings).
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
            "SL",
            "SLKORT",
            "SL ACCESS",
            "UL",
            "SKANETRAFIKEN",
            "SKÅNETRAFIKEN",
            "VASTTRAFIK",
            "VÄSTTRAFIK",
            "UBER",
            "BOLT",
            "TAXI",
            "CIRCLE K",
            "PREEM",
            "OKQ8",
            "SHELL",
            "INGO",
            "SJ",
            "SJ AB",
            "MTRX",
            "FLIXBUS",
            "DSB",
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
            "HM",
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
            "LON",
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

_INTERNAL_TRANSFER_KEYWORDS = [
    "ÖVERFÖRING",
    "OVERFORING",
    "TRANSFER",
    "EGNA KONTON",
    "XTRASPAR",
    "AVANZA",
    "NORDNET",
]


def is_internal_transfer(description: str) -> bool:
    """True for moves between the user's own accounts (not payments to others)."""
    return any(phrase_matches(w, description) for w in _INTERNAL_TRANSFER_KEYWORDS)


def is_swish_payment(description: str, amount: float) -> bool:
    """True when Swish is an outgoing payment to another person, not an account move."""
    if amount >= 0 or not phrase_matches("SWISH", description):
        return False
    if is_internal_transfer(description):
        return False
    return True


@dataclass
class CategoryResult:
    category: str
    source: str  # learned | auto | unclear
    confidence: float
    needs_review: bool
    transfer_kind: str | None = None


def resolve_transfer_kind(category: str, description: str) -> str | None:
    if category != "Transfers":
        return None
    if is_internal_transfer(description):
        return "internal"
    return None


def _finalize(result: CategoryResult, description: str) -> CategoryResult:
    tk = resolve_transfer_kind(result.category, description)
    if tk == result.transfer_kind:
        return result
    return CategoryResult(
        result.category,
        result.source,
        result.confidence,
        result.needs_review,
        tk,
    )


def categorize(
    description: str,
    amount: float,
    learned_rules: list[tuple[str, str]],
    *,
    foodora_threshold: float | None = None,
) -> CategoryResult:
    """Return category attempt. learned_rules: list of (match_text, category)."""
    for match_text, category in learned_rules:
        if phrase_matches(match_text, description):
            return _finalize(CategoryResult(category, "learned", _HIGH, False), description)

    if is_internal_transfer(description):
        return CategoryResult("Transfers", "auto", _HIGH, False, transfer_kind="internal")

    if is_swish_payment(description, amount):
        return CategoryResult("Other", "auto", _HIGH, False)

    if amount > 0 and phrase_matches("SWISH", description):
        # Incoming Swish from another person — not salary; let user classify
        return CategoryResult("Unclear", "unclear", _LOW, True)

    if amount > 0:
        # Income heuristic when description weak
        for cat, words in _BUILTIN:
            if cat != "Income":
                continue
            for w in words:
                if phrase_matches(w, description):
                    return CategoryResult("Income", "auto", _HIGH, False)

    best: CategoryResult | None = None
    for category, words in _BUILTIN:
        for w in words:
            token = w.strip()
            if not token:
                continue
            if phrase_matches(token, description):
                conf = _HIGH if len(token.replace(" ", "")) >= 5 else _MED
                # Short transit brands (SJ, SL) are still reliable as whole tokens
                if category == "Transport" and len(token) <= 3:
                    conf = _HIGH
                candidate = CategoryResult(category, "auto", conf, conf < _UNCLEAR_THRESHOLD)
                if best is None or candidate.confidence > best.confidence:
                    best = candidate

    if best is None:
        return CategoryResult("Unclear", "unclear", _LOW, True)

    # Foodora amount split: large orders are groceries, not restaurants
    if best.category == "Restaurants" and phrase_matches("FOODORA", description):
        threshold = float(
            foodora_threshold if foodora_threshold is not None
            else get_setting("foodora_grocery_threshold", _DEFAULT_FOODORA_THRESHOLD)
        )
        if abs(amount) >= threshold:
            best = CategoryResult("Groceries", "auto", _HIGH, False)

    if best.confidence < _UNCLEAR_THRESHOLD:
        return CategoryResult(
            best.category if best.category != "Unclear" else "Unclear",
            "unclear",
            best.confidence,
            True,
        )

    # Clear keyword / amount heuristics: trust them; only Unclear goes to review queue
    return _finalize(best, description)


def ensure_category(name: str) -> str:
    from .categories import ensure_category_slug

    return ensure_category_slug(name)
