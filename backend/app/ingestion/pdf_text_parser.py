"""Text-PDF statement parsing.

Strategy:
1. pdfplumber table extraction — when the PDF has ruled/detectable tables,
   convert them to header→value rows and reuse the bank adapters.
2. Line-regex fallback — parse "date ... description ... amounts" lines from
   raw text (also reused by the OCR parser).
3. camelot (optional dependency) as a last-ditch table extractor.

Opening/closing balances are read from "Opening Balance ..." / "Closing
Balance ..." lines when printed.
"""
import re
from datetime import datetime

from .adapters import pick_adapter
from .normalize import parse_money_minor
from .types import ParsedStatement, RawTxn

_OPENING_RE = re.compile(r"opening\s+balance[^\d\-(]*([\d,.\-()]+)", re.I)
_CLOSING_RE = re.compile(r"closing\s+balance[^\d\-(]*([\d,.\-()]+)", re.I)

_DATE_PATTERNS = [
    (re.compile(r"^(\d{2}-[A-Za-z]{3}-\d{4})\b"), "%d-%b-%Y"),
    (re.compile(r"^(\d{2}/\d{2}/\d{4})\b"), "%d/%m/%Y"),
    (re.compile(r"^(\d{4}-\d{2}-\d{2})\b"), "%Y-%m-%d"),
    (re.compile(r"^(\d{2}-\d{2}-\d{4})\b"), "%d-%m-%Y"),
]
_MONEY_RE = re.compile(r"\(?-?\d{1,3}(?:,\d{3})*\.\d{2}\)?(?:\s*[CD][Rr])?")


def parse_statement_text(text: str) -> ParsedStatement:
    """Parse plain statement text line by line (shared with the OCR path).

    Expected line shape: DATE  DESCRIPTION  [DEBIT|CREDIT]  BALANCE — i.e. the
    last money figure on a line is the running balance and the one before it
    is the transaction amount. Lines whose balance decreases are outflows.
    """
    opening = closing = None
    rows: list[RawTxn] = []
    prev_balance: int | None = None

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if (m := _OPENING_RE.search(line)) and opening is None:
            opening = parse_money_minor(m.group(1))
            if prev_balance is None:
                prev_balance = opening
            continue
        if (m := _CLOSING_RE.search(line)) and closing is None:
            closing = parse_money_minor(m.group(1))
            continue

        txn_date = None
        rest = line
        for pattern, fmt in _DATE_PATTERNS:
            if m := pattern.match(line):
                try:
                    txn_date = datetime.strptime(m.group(1), fmt).date()
                except ValueError:
                    continue
                rest = line[m.end():].strip()
                break
        if txn_date is None:
            continue

        monies = _MONEY_RE.findall(rest)
        if not monies:
            continue
        balance = parse_money_minor(monies[-1])
        if len(monies) >= 2:
            amount = parse_money_minor(monies[-2])
        else:
            amount = None
        if amount is None or balance is None:
            continue

        # Statements print amounts unsigned; recover the sign from the
        # running balance when available.
        amount = abs(amount)
        if prev_balance is not None and balance < prev_balance:
            amount = -amount
        elif prev_balance is None and closing is None:
            # No baseline: assume listed first amount keeps printed sign.
            pass
        prev_balance = balance

        description = _MONEY_RE.sub("", rest).strip(" -|")
        rows.append(
            RawTxn(
                txn_date=txn_date,
                amount_minor=amount,
                description=description,
                balance_after_minor=balance,
            )
        )

    statement = ParsedStatement(
        rows=rows, opening_balance_minor=opening, closing_balance_minor=closing
    )
    statement.infer_balances()
    return statement


def _tables_to_statement(tables: list[list[list[str | None]]]) -> ParsedStatement | None:
    for table in tables:
        if not table or len(table) < 2:
            continue
        headers = [(h or "").strip() for h in table[0]]
        if sum(1 for h in headers if h) < 3:
            continue
        data_rows = [
            {h: (c or "").strip() for h, c in zip(headers, row)} for row in table[1:]
        ]
        adapter = pick_adapter(headers)
        rows = adapter.parse_rows(data_rows)
        if rows:
            statement = ParsedStatement(rows=rows, bank_hint=adapter.name)
            statement.infer_balances()
            return statement
    return None


def parse_pdf_text(path: str) -> ParsedStatement:
    import pdfplumber

    with pdfplumber.open(path) as pdf:
        full_text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        tables = [t for page in pdf.pages for t in (page.extract_tables() or [])]

    statement = _tables_to_statement(tables)
    if statement is not None and statement.rows:
        # Balances may only appear in the prose around the table.
        if statement.opening_balance_minor is None:
            if m := _OPENING_RE.search(full_text):
                statement.opening_balance_minor = parse_money_minor(m.group(1))
        if statement.closing_balance_minor is None:
            if m := _CLOSING_RE.search(full_text):
                statement.closing_balance_minor = parse_money_minor(m.group(1))
        return statement

    statement = parse_statement_text(full_text)
    if statement.rows:
        return statement

    # Optional last resort: camelot handles some ruled tables pdfplumber misses.
    try:
        import camelot  # type: ignore

        found = camelot.read_pdf(path, pages="all", flavor="lattice")
        tables = [t.df.values.tolist() for t in found]
        if not tables:
            found = camelot.read_pdf(path, pages="all", flavor="stream")
            tables = [t.df.values.tolist() for t in found]
        statement = _tables_to_statement(
            [[list(map(str, row)) for row in t] for t in tables]
        ) or statement
    except ImportError:
        pass
    return statement
