"""Meezan Bank statement layout.

Header signature:
    Transaction Date | Description | Withdrawal Amount | Deposit Amount | Available Balance
Dates like 05/01/2026 (day first); amounts like 2,000.00.
"""
from ..normalize import parse_money_minor
from ..types import RawTxn
from .base import BankAdapter

DATE_FORMATS = ["%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"]
SIGNATURE = {"transaction date", "description", "withdrawal amount", "deposit amount"}


class MeezanAdapter(BankAdapter):
    name = "meezan"

    def matches(self, headers: list[str]) -> bool:
        normalized = {h.strip().lower() for h in headers}
        return SIGNATURE <= normalized

    def parse_rows(self, rows: list[dict[str, str]]) -> list[RawTxn]:
        txns: list[RawTxn] = []
        for row in rows:
            r = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            d = self.parse_date(r.get("transaction date", ""), DATE_FORMATS)
            if d is None:
                continue
            withdrawal = parse_money_minor(r.get("withdrawal amount"))
            deposit = parse_money_minor(r.get("deposit amount"))
            if withdrawal is None and deposit is None:
                continue
            amount = (deposit or 0) - (withdrawal or 0)
            txns.append(
                RawTxn(
                    txn_date=d,
                    amount_minor=amount,
                    description=r.get("description", ""),
                    balance_after_minor=parse_money_minor(r.get("available balance")),
                )
            )
        return txns
