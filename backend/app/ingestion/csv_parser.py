"""CSV statement parsing.

Statements often carry metadata lines above the header (account name, opening
balance). We scan for the first plausible header row, capture any stated
opening/closing balances from the preamble, then hand data rows to the
matching bank adapter.
"""
import csv
import io
import re

from .adapters import pick_adapter
from .normalize import parse_money_minor
from .types import ParsedStatement

_OPENING_RE = re.compile(r"opening\s+balance[^\d\-(]*([\d,.\-()]+)", re.I)
_CLOSING_RE = re.compile(r"closing\s+balance[^\d\-(]*([\d,.\-()]+)", re.I)

_HEADER_HINTS = ("date", "description", "particulars", "debit", "credit",
                 "withdrawal", "deposit", "amount", "balance")


def _looks_like_header(cells: list[str]) -> bool:
    lowered = [c.strip().lower() for c in cells if c.strip()]
    hits = sum(1 for c in lowered if any(h in c for h in _HEADER_HINTS))
    return len(lowered) >= 3 and hits >= 2


def parse_csv(content: bytes | str) -> ParsedStatement:
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    raw_rows = list(csv.reader(io.StringIO(text)))

    opening = closing = None
    header_idx = None
    for i, cells in enumerate(raw_rows):
        line = ",".join(cells)
        if (m := _OPENING_RE.search(line)) and opening is None:
            opening = parse_money_minor(m.group(1))
        if (m := _CLOSING_RE.search(line)) and closing is None:
            closing = parse_money_minor(m.group(1))
        if header_idx is None and _looks_like_header(cells):
            header_idx = i
    if header_idx is None:
        return ParsedStatement(rows=[], opening_balance_minor=opening,
                               closing_balance_minor=closing)

    headers = [h.strip() for h in raw_rows[header_idx]]
    data_rows = [
        dict(zip(headers, row))
        for row in raw_rows[header_idx + 1:]
        if any(cell.strip() for cell in row)
    ]

    adapter = pick_adapter(headers)
    statement = ParsedStatement(
        rows=adapter.parse_rows(data_rows),
        opening_balance_minor=opening,
        closing_balance_minor=closing,
        bank_hint=adapter.name,
    )
    statement.infer_balances()
    return statement
