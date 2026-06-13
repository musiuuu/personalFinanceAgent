"""Pydantic I/O models for every engine function and tool.

The engine operates on `Txn` (a plain value object), never on ORM rows,
so every engine function stays pure and trivially testable.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .models import Category

# ---------------------------------------------------------------- core values


class Txn(BaseModel):
    """Minimal transaction view the engine computes over."""

    txn_date: date
    amount_minor: int  # signed: negative = outflow
    category: Category = Category.OTHER
    merchant: str | None = None
    raw_description: str = ""
    txn_id: int | None = None


class YearMonth(BaseModel):
    year: int = Field(ge=1900, le=3000)
    month: int = Field(ge=1, le=12)

    @classmethod
    def of(cls, d: date) -> "YearMonth":
        return cls(year=d.year, month=d.month)

    @classmethod
    def parse(cls, s: str) -> "YearMonth":
        y, m = s.split("-")
        return cls(year=int(y), month=int(m))

    def contains(self, d: date) -> bool:
        return d.year == self.year and d.month == self.month

    def next(self) -> "YearMonth":
        if self.month == 12:
            return YearMonth(year=self.year + 1, month=1)
        return YearMonth(year=self.year, month=self.month + 1)

    def prev(self) -> "YearMonth":
        if self.month == 1:
            return YearMonth(year=self.year - 1, month=12)
        return YearMonth(year=self.year, month=self.month - 1)

    def __str__(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    def __hash__(self) -> int:
        return hash((self.year, self.month))

    def __le__(self, other: "YearMonth") -> bool:
        return (self.year, self.month) <= (other.year, other.month)

    def __lt__(self, other: "YearMonth") -> bool:
        return (self.year, self.month) < (other.year, other.month)


def months_between(a: YearMonth, b: YearMonth) -> int:
    """Whole months from a to b (b >= a → positive)."""
    return (b.year - a.year) * 12 + (b.month - a.month)


# ------------------------------------------------------------------ cashflow


class CashflowResult(BaseModel):
    month: YearMonth
    income_minor: int  # sum of inflows (positive)
    expense_minor: int  # sum of outflow magnitudes (positive)
    net_minor: int  # income - expense
    by_category: dict[Category, int]  # expense magnitudes per category
    income_by_category: dict[Category, int]
    txn_count: int


class CategoryDelta(BaseModel):
    category: Category
    amount_a_minor: int
    amount_b_minor: int
    delta_minor: int  # b - a (positive = spent more in b)


class CashflowDelta(BaseModel):
    month_a: YearMonth
    month_b: YearMonth
    net_a_minor: int
    net_b_minor: int
    net_delta_minor: int
    income_delta_minor: int
    expense_delta_minor: int
    category_deltas: list[CategoryDelta]  # ranked by |delta| desc


# ------------------------------------------------------------------ recurring


class RecurringGroup(BaseModel):
    group_id: str
    merchant: str
    cadence_days: int  # 7, 30 or 365
    typical_amount_minor: int  # median, signed
    occurrences: int
    first_date: date
    last_date: date
    monthly_equivalent_minor: int  # signed, normalized to per-month
    price_change: bool = False
    price_change_pct: float | None = None
    last_amount_minor: int | None = None
    txn_ids: list[int] = []


# ------------------------------------------------------------------ forecast


class Forecast(BaseModel):
    """All figures are per-month expectations in minor units (positive)."""

    expected_income_minor: int
    expected_recurring_minor: int  # known/recurring outflows
    expected_variable_minor: int  # trailing-median variable outflows
    by_category_variable: dict[Category, int]
    recurring_items: list[RecurringGroup] = []
    lookback_months: int
    as_of: date

    @property
    def expected_surplus_minor(self) -> int:
        return (
            self.expected_income_minor
            - self.expected_recurring_minor
            - self.expected_variable_minor
        )


# -------------------------------------------------------------- affordability


class AffordabilityResult(BaseModel):
    affordable: bool
    purchase_minor: int
    target_date: date
    months_until_target: int
    current_balance_minor: int
    expected_income_total_minor: int
    expected_recurring_total_minor: int
    expected_variable_total_minor: int
    projected_balance_minor: int  # before the purchase
    balance_after_purchase_minor: int
    safety_buffer_minor: int
    shortfall_minor: int  # 0 when affordable


# --------------------------------------------------------------- savings plan


class SuggestedCut(BaseModel):
    category: Category
    current_monthly_minor: int
    suggested_cut_minor: int


class SavingsMonth(BaseModel):
    month_index: int  # 1-based
    save_minor: int
    cumulative_saved_minor: int
    projected_balance_minor: int


class SavingsPlan(BaseModel):
    feasible: bool
    goal_minor: int
    already_saved_minor: int
    horizon_months: int
    required_monthly_minor: int
    monthly_surplus_minor: int
    gap_minor: int  # 0 when feasible
    suggested_cuts: list[SuggestedCut]
    schedule: list[SavingsMonth]


# ----------------------------------------------------------------- simulation


class ScenarioDelta(BaseModel):
    type: Literal["cut_category", "cancel", "add_expense", "income_change"]
    category: Category | None = None
    merchant: str | None = None
    pct: float | None = Field(default=None, ge=0, le=100)
    amount_minor: int | None = None
    recurring: bool = True

    @model_validator(mode="after")
    def _check_required_fields(self) -> "ScenarioDelta":
        if self.type == "cut_category" and (self.category is None or self.pct is None):
            raise ValueError("cut_category requires category and pct")
        if self.type == "cancel" and not self.merchant:
            raise ValueError("cancel requires merchant")
        if self.type in ("add_expense", "income_change") and self.amount_minor is None:
            raise ValueError(f"{self.type} requires amount_minor")
        return self


class SimMonth(BaseModel):
    month_index: int  # 1-based
    balance_before_minor: int  # baseline projected balance
    balance_after_minor: int  # scenario projected balance
    delta_minor: int


class SimResult(BaseModel):
    horizon_months: int
    baseline_monthly_net_minor: int
    scenario_monthly_net_minor: int
    monthly_impact_minor: int
    months: list[SimMonth]
    applied: list[ScenarioDelta]
    notes: list[str] = []


# ------------------------------------------------------------------ anomalies


class Anomaly(BaseModel):
    txn_id: int | None
    txn_date: date
    merchant: str | None
    amount_minor: int
    category: Category
    kind: Literal[
        "robust_outlier", "new_large_merchant", "duplicate_charge", "recurring_price_spike"
    ]
    reason: str


# ------------------------------------------------------------------ reconcile


class ReconcileResult(BaseModel):
    ok: bool
    opening_balance_minor: int
    txn_sum_minor: int
    expected_closing_minor: int
    stated_closing_minor: int
    discrepancy_minor: int  # stated - expected; 0 when ok
