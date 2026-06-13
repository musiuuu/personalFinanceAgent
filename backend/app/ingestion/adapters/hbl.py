"""HBL (Habib Bank Limited) statement layout.

Header signature:
    Date | Value Date | Particulars | Chq No | Debit | Credit | Balance
Dates like 01-Jan-2026; amounts like 60,000.00 with separate Debit/Credit
columns; running Balance column.
"""
from ..normalize import parse_money_minor
from ..types import RawTxn
from .base import BankAdapter

DATE_FORMATS = ["%d-%b-%Y", "%d-%b-%y", "%d-%m-%Y"]
SIGNATURE = {"date", "particulars", "debit", "credit", "balance"}


class HBLAdapter(BankAdapter):
    name = "hbl"

    def matches(self, headers: list[str]) -> bool:
        normalized = {h.strip().lower() for h in headers}
        return SIGNATURE <= normalized

    def parse_rows(self, rows: list[dict[str, str]]) -> list[RawTxn]:
        txns: list[RawTxn] = []
        for row in rows:
            r = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            d = self.parse_date(r.get("date", ""), DATE_FORMATS)
            if d is None:
                continue  # footer/section rows
            debit = parse_money_minor(r.get("debit"))
            credit = parse_money_minor(r.get("credit"))
            if debit is None and credit is None:
                continue
            amount = (credit or 0) - (debit or 0)
            txns.append(
                RawTxn(
                    txn_date=d,
                    amount_minor=amount,
                    description=r.get("particulars", ""),
                    balance_after_minor=parse_money_minor(r.get("balance")),
                )
            )
        return txns
