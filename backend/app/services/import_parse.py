from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from ..config import MAX_IMPORT_ROWS


@dataclass
class ParsedRow:
    tx_date: str  # ISO date
    amount: float
    description: str


@dataclass
class ColumnMapping:
    date: str
    amount: str
    description: str
    date_format: str | None = None  # e.g. %Y-%m-%d, %Y%m%d, auto
    amount_decimal: str = ","  # Swedish often uses comma
    delimiter: str | None = None


def sniff_csv(text: str) -> tuple[list[str], list[dict[str, str]], str]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    rows = []
    for i, row in enumerate(reader):
        rows.append({k: (v or "").strip() for k, v in row.items() if k is not None})
        if i >= 24:
            break
    return headers, rows, delimiter


def read_tabular(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
        if not raw_rows:
            return [], [], ","
        headers = [str(c).strip() if c is not None else f"col{i}" for i, c in enumerate(raw_rows[0])]
        preview = []
        for row in raw_rows[1:26]:
            preview.append(
                {
                    headers[i]: "" if (i >= len(row) or row[i] is None) else str(row[i]).strip()
                    for i in range(len(headers))
                }
            )
        return headers, preview, "xlsx"

    text = path.read_text(encoding="utf-8-sig", errors="replace")
    return sniff_csv(text)


def _parse_amount(raw: str, decimal: str = ",") -> float:
    s = raw.strip().replace(" ", "").replace("\u00a0", "")
    if not s:
        raise ValueError("empty amount")
    # Handle 1.234,56 vs 1,234.56
    if decimal == ",":
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    # Parentheses negative
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    return float(s)


def _parse_date(raw: str, fmt: str | None) -> str:
    s = raw.strip()
    if not s:
        raise ValueError("empty date")
    formats = []
    if fmt and fmt != "auto":
        formats.append(fmt)
    formats.extend(
        [
            "%Y-%m-%d",
            "%Y%m%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%d.%m.%Y",
            "%Y/%m/%d",
            "%d/%m/%y",
            "%m/%d/%Y",
        ]
    )
    # Excel serial sometimes comes as float string
    try:
        as_float = float(s)
        if 30000 < as_float < 60000:
            from datetime import date, timedelta

            base = date(1899, 12, 30)
            return (base + timedelta(days=int(as_float))).isoformat()
    except ValueError:
        pass

    for f in formats:
        try:
            return datetime.strptime(s[:19], f).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"unparseable date: {raw!r}")


def parse_all_rows(path: Path, mapping: ColumnMapping) -> list[ParsedRow]:
    suffix = path.suffix.lower()
    rows_dicts: list[dict[str, Any]] = []

    if suffix in {".xlsx", ".xlsm"}:
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        headers: list[str] = []
        row_count = 0
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i == 0:
                headers = [
                    str(c).strip() if c is not None else f"col{j}" for j, c in enumerate(row)
                ]
                continue
            d = {
                headers[j]: "" if (j >= len(row) or row[j] is None) else str(row[j]).strip()
                for j in range(len(headers))
            }
            if any(d.values()):
                row_count += 1
                if row_count > MAX_IMPORT_ROWS:
                    raise ValueError(f"Too many rows (max {MAX_IMPORT_ROWS:,})")
                rows_dicts.append(d)
    else:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        delimiter = mapping.delimiter
        if not delimiter:
            _, _, delimiter = sniff_csv(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        for row in reader:
            d = {k: (v or "").strip() for k, v in row.items() if k is not None}
            if any(d.values()):
                if len(rows_dicts) >= MAX_IMPORT_ROWS:
                    raise ValueError(f"Too many rows (max {MAX_IMPORT_ROWS:,})")
                rows_dicts.append(d)

    parsed: list[ParsedRow] = []
    for d in rows_dicts:
        try:
            tx_date = _parse_date(str(d.get(mapping.date, "")), mapping.date_format)
            amount = _parse_amount(str(d.get(mapping.amount, "")), mapping.amount_decimal)
            desc = str(d.get(mapping.description, "")).strip() or "(no description)"
            parsed.append(ParsedRow(tx_date=tx_date, amount=amount, description=desc))
        except (ValueError, TypeError, KeyError):
            continue
    return parsed


def guess_mapping(headers: list[str]) -> dict[str, str | None]:
    lower = {h: h.lower() for h in headers}

    def find(*needles: str) -> str | None:
        for h, lh in lower.items():
            for n in needles:
                if n in lh:
                    return h
        return None

    return {
        "date": find("bokföringsdag", "bokforingsdag", "transaktionsdag", "datum", "date", "valutadag"),
        "amount": find("belopp", "amount", "summa"),
        "description": find("text", "beskrivning", "description", "mottagare", "meddelande", "narrativ"),
    }
