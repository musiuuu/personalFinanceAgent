"""Heuristic adapter for unknown statement layouts.

Column roles are inferred from the data itself:
- date column   → the column whose values parse as dates most often
- amount column → numeric column with currency-like values; or a
                  Debit/Credit column pair detected by header keywords
- description   → the longest mostly-text column
- balance       → numeric column whose header mentions balance
"""
from datetime import date

from ..normalize import parse_money_minor
from ..types import RawTxn
from .base import BankAdapter

DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d-%b-%Y", "%d %b %Y",
    "%m/%d/%Y", "%d/%m/%y", "%d-%b-%y",
]

DEBIT_WORDS = ("debit", "withdrawal", "dr")
CREDIT_WORDS = ("credit", "deposit", "cr")
BALANCE_WORDS = ("balance",)
AMOUNT_WORDS = ("amount", "value")


class GenericAdapter(BankAdapter):
    name = "generic"

    def matches(self, headers: list[str]) -> bool:
        return True  # last resort

    # ------------------------------------------------------------ inference

    def _date_column(self, headers: list[str], rows: list[dict[str, str]]) -> str | None:
        best, best_hits = None, 0
        for h in headers:
            hits = sum(
                1 for row in rows[:25]
                if self.parse_date((row.get(h) or "").strip(), DATE_FORMATS)
            )
            if hits > best_hits:
                best, best_hits = h, hits
        return best if best_hits >= max(1, min(len(rows), 25) // 2) else None

    def _numeric_score(self, h: str, rows: list[dict[str, str]]) -> float:
        vals = [(row.get(h) or "").strip() for row in rows[:25]]
        vals = [v for v in vals if v not in ("", "-")]
        if not vals:
            return 0.0
        ok = sum(1 for v in vals if parse_money_minor(v) is not None)
        return ok / len(vals)

    def _description_column(self, headers: list[str], rows: list[dict[str, str]]) -> str | None:
        best, best_len = None, -1.0
        for h in headers:
            vals = [(row.get(h) or "") for row in rows[:25]]
            texty = [v for v in vals if v and parse_money_minor(v) is None
                     and not self.parse_date(v.strip(), DATE_FORMATS)]
            if not texty:
                continue
            avg_len = sum(len(v) for v in texty) / len(texty)
            if avg_len > best_len:
                best, best_len = h, avg_len
        return best

    # --------------------------------------------------------------- parse

    def parse_rows(self, rows: list[dict[str, str]]) -> list[RawTxn]:
        if not rows:
            return []
        headers = list(rows[0].keys())
        lower = {h: h.strip().lower() for h in headers}

        date_col = self._date_column(headers, rows)
        if date_col is None:
            return []
        desc_col = self._description_column(
            [h for h in headers if h != date_col], rows
        )

        balance_col = next(
            (h for h in headers if any(w in lower[h] for w in BALANCE_WORDS)
             and self._numeric_score(h, rows) > 0.5),
            None,
        )
        debit_col = next(
            (h for h in headers if any(w in lower[h] for w in DEBIT_WORDS)
             and h != balance_col), None,
        )
        credit_col = next(
            (h for h in headers if any(w in lower[h] for w in CREDIT_WORDS)
             and h != balance_col), None,
        )
        amount_col = None
        if debit_col is None or credit_col is None:
            candidates = [
                h for h in headers
                if h not in (date_col, desc_col, balance_col)
                and (any(w in lower[h] for w in AMOUNT_WORDS)
                     or self._numeric_score(h, rows) > 0.8)
            ]
            amount_col = candidates[0] if candidates else None

        txns: list[RawTxn] = []
        for row in rows:
            d = self.parse_date((row.get(date_col) or "").strip(), DATE_FORMATS)
            if d is None:
                continue
            amount = self._row_amount(row, debit_col, credit_col, amount_col)
            if amount is None:
                continue
            txns.append(
                RawTxn(
                    txn_date=d,
                    amount_minor=amount,
                    description=(row.get(desc_col) or "").strip() if desc_col else "",
                    balance_after_minor=(
                        parse_money_minor(row.get(balance_col)) if balance_col else None
                    ),
                )
            )
        return txns

    def _row_amount(self, row, debit_col, credit_col, amount_col) -> int | None:
        if debit_col is not None and credit_col is not None:
            debit = parse_money_minor(row.get(debit_col))
            credit = parse_money_minor(row.get(credit_col))
            if debit is None and credit is None:
                return None
            return (credit or 0) - abs(debit or 0)
        if amount_col is not None:
            return parse_money_minor(row.get(amount_col))
        return None
