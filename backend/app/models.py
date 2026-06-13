"""SQLModel tables. All money is integer minor units (paisa)."""
from datetime import date, datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class Category(str, Enum):
    INCOME = "INCOME"
    SALARY = "SALARY"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
    GROCERIES = "GROCERIES"
    DINING = "DINING"
    TRANSPORT = "TRANSPORT"
    FUEL = "FUEL"
    UTILITIES = "UTILITIES"
    RENT = "RENT"
    SUBSCRIPTIONS = "SUBSCRIPTIONS"
    SHOPPING = "SHOPPING"
    HEALTH = "HEALTH"
    EDUCATION = "EDUCATION"
    TRAVEL = "TRAVEL"
    ENTERTAINMENT = "ENTERTAINMENT"
    FEES_CHARGES = "FEES_CHARGES"
    CASH_WITHDRAWAL = "CASH_WITHDRAWAL"
    OTHER = "OTHER"


INCOME_CATEGORIES = {Category.INCOME, Category.SALARY, Category.TRANSFER_IN}


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    currency: str = "PKR"
    opening_balance_minor: int = 0
    opening_balance_date: date | None = None


class Document(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    filename: str
    file_type: str  # csv | pdf_text | pdf_ocr | invoice
    account_id: int | None = Field(default=None, foreign_key="account.id")
    statement_period_start: date | None = None
    statement_period_end: date | None = None
    opening_balance_minor: int | None = None
    closing_balance_minor: int | None = None  # as printed on the statement
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "parsed"  # parsed | reconciled | failed
    reconcile_discrepancy_minor: int | None = None


class Transaction(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id")
    source_doc_id: int = Field(foreign_key="document.id")
    txn_date: date = Field(index=True)
    amount_minor: int  # signed: negative = outflow
    currency: str = "PKR"
    raw_description: str
    merchant_normalized: str | None = Field(default=None, index=True)
    category: str | None = Field(default=None, index=True)
    subcategory: str | None = None
    balance_after_minor: int | None = None
    is_recurring: bool = False
    recurring_group_id: str | None = None
    is_anomaly: bool = False
    anomaly_reason: str | None = None
    dedup_hash: str = Field(unique=True, index=True)


class Budget(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    category: str
    monthly_limit_minor: int


class Goal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    target_amount_minor: int
    target_date: date
    created_at: date = Field(default_factory=date.today)
    saved_so_far_minor: int = 0


class DocChunk(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    source_doc_id: int = Field(foreign_key="document.id")
    text: str
    embedding: bytes


class MerchantCategoryCache(SQLModel, table=True):
    """Cache of LLM categorizations so each unknown merchant is classified once."""

    id: int | None = Field(default=None, primary_key=True)
    merchant_normalized: str = Field(unique=True, index=True)
    category: str
    source: str = "llm"  # llm | manual
