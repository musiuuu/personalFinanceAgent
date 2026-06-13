"""Intermediate shapes shared by parsers and adapters."""
from datetime import date

from pydantic import BaseModel


class RawTxn(BaseModel):
    txn_date: date
    amount_minor: int  # signed: negative = outflow
    description: str
    balance_after_minor: int | None = None


class ParsedStatement(BaseModel):
    rows: list[RawTxn]
    opening_balance_minor: int | None = None
    closing_balance_minor: int | None = None
    period_start: date | None = None
    period_end: date | None = None
    bank_hint: str | None = None

    def infer_balances(self) -> None:
        """Derive opening/closing from the running-balance column when the
        statement doesn't print them separately."""
        rows_with_balance = [r for r in self.rows if r.balance_after_minor is not None]
        if not rows_with_balance:
            return
        first, last = self.rows[0], self.rows[-1]
        if self.opening_balance_minor is None and first.balance_after_minor is not None:
            self.opening_balance_minor = first.balance_after_minor - first.amount_minor
        if self.closing_balance_minor is None and last.balance_after_minor is not None:
            self.closing_balance_minor = last.balance_after_minor
        if self.rows:
            self.period_start = self.period_start or min(r.txn_date for r in self.rows)
            self.period_end = self.period_end or max(r.txn_date for r in self.rows)
