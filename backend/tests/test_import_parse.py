"""Regression tests for bank CSV/Excel amount and date parsing."""

from decimal import Decimal
from pathlib import Path

from app.services.import_parse import (
    ColumnMapping,
    _coerce_amount,
    _parse_amount,
    detect_amount_decimal,
    guess_amount_decimal,
    guess_mapping,
    parse_all_rows,
)


def test_swedish_comma_amounts_not_multiplied():
    """Swedish ``-39,00`` must stay -39 even if UI hint wrongly says '.'."""
    assert _parse_amount("-39,00", ",") == -39.0
    assert _parse_amount("-39,00", ".") == -39.0  # wrong hint must not 100×
    assert _parse_amount("-219,00", ".") == -219.0
    assert _parse_amount("-263,10", ".") == -263.1
    assert _parse_amount("-2067,00", ".") == -2067.0
    assert _parse_amount("-1.234,56", ",") == -1234.56
    assert _parse_amount("1.500.000,00", ",") == 1_500_000.0


def test_dot_decimal_amounts_not_multiplied_under_comma_hint():
    """Excel/US ``-39.00`` must stay -39 even with Swedish comma hint."""
    assert _parse_amount("-39.00", ",") == -39.0
    assert _parse_amount("-219.00", ",") == -219.0
    assert _parse_amount("-1,234.56", ".") == -1234.56
    assert _parse_amount("-1,234.56", ",") == -1234.56


def test_coerce_amount_accepts_native_numbers():
    assert _coerce_amount(-39.0, ",") == -39.0
    assert _coerce_amount(Decimal("-263.10"), ",") == -263.1
    assert _coerce_amount(-219, ".") == -219.0


def test_detect_and_guess_decimal_from_swedish_samples():
    samples = ["-39,00", "-219,00", "15000,00", "-1.234,56"]
    assert guess_amount_decimal(samples) == ","
    assert detect_amount_decimal("-39,00", hint=".") == ","


def test_guess_mapping_prefers_beskrivning_over_mottagare():
    headers = [
        "Bokföringsdag",
        "Belopp",
        "Avsändare",
        "Mottagare",
        "Namn",
        "Beskrivning",
        "Saldo",
        "Valuta",
    ]
    guessed = guess_mapping(headers)
    assert guessed["date"] == "Bokföringsdag"
    assert guessed["amount"] == "Belopp"
    assert guessed["description"] == "Beskrivning"


def test_swedbank_like_csv_import(tmp_path: Path):
    csv_text = """Bokföringsdag;Belopp;Avsändare;Mottagare;Namn;Beskrivning;Saldo;Valuta;
2026/07/19;-39,00;;;;Kortköp 260719 TOO GOOD TO GO;10000,00;SEK;
2026/07/19;-219,00;;;;Kortköp 260719 FOODORA AB;10219,00;SEK;
2026/07/18;-263,10;;;;Kortköp 260718 FOODORA AB;10482,10;SEK;
2026/07/17;-2067,00;;;;Kortköp ZALANDO PAYMENTS GM;12549,10;SEK;
2026/07/16;-6500,00;;;Erik Engebretsen;Swish betalning Erik Engebretsen;19049,10;SEK;
2026/07/15;15000,00;;;;Överföring;34049,10;SEK;
"""
    path = tmp_path / "bank.csv"
    path.write_text(csv_text, encoding="utf-8")

    # Reproduce the bug condition: wrong decimal hint "."
    mapping = ColumnMapping(
        date="Bokföringsdag",
        amount="Belopp",
        description="Beskrivning",
        amount_decimal=".",
        delimiter=";",
    )
    rows = parse_all_rows(path, mapping)
    by_desc = {r.description: r.amount for r in rows}
    assert by_desc["Kortköp 260719 TOO GOOD TO GO"] == -39.0
    assert by_desc["Kortköp 260719 FOODORA AB"] == -219.0
    assert by_desc["Kortköp 260718 FOODORA AB"] == -263.1
    assert by_desc["Kortköp ZALANDO PAYMENTS GM"] == -2067.0
    assert by_desc["Swish betalning Erik Engebretsen"] == -6500.0
    assert by_desc["Överföring"] == 15000.0


def test_currency_suffix_stripped():
    assert _parse_amount("-39,00 SEK", ",") == -39.0
    assert _parse_amount("219.00 kr", ".") == 219.0
