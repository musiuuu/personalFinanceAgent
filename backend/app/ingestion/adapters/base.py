"""Adapter contract: map a bank's raw tabular rows to canonical RawTxn."""
from abc import ABC, abstractmethod
from datetime import date, datetime

from ..types import RawTxn


class BankAdapter(ABC):
    name: str = "base"

    @abstractmethod
    def matches(self, headers: list[str]) -> bool:
        """Does this adapter recognize the statement's header signature?"""

    @abstractmethod
    def parse_rows(self, rows: list[dict[str, str]]) -> list[RawTxn]:
        """Map raw header→value rows to canonical transactions."""

    @staticmethod
    def parse_date(value: str, formats: list[str]) -> date | None:
        s = (value or "").strip()
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None
