"""Per-month forecast of income and expenses.

Modeling choice (deliberate, documented):
- Recurring/known outflows = sum of monthly-equivalents of detected recurring
  groups (see recurring.py).
- Variable outflows = trailing MEDIAN of the last `n_lookback` full months of
  non-recurring spend, per category. Median, not mean — robust to one-off
  spikes such as a single large purchase.
- Income = trailing median of monthly inflows over the same window.
"""
from datetime import date
from statistics import median

from ..models import Category
from ..schemas import Forecast, Txn, YearMonth
from .recurring import detect_recurring


def _trailing_months(as_of: date, n: int) -> list[YearMonth]:
    """The n full months strictly before the month of `as_of`, oldest first."""
    months: list[YearMonth] = []
    m = YearMonth.of(as_of).prev()
    for _ in range(n):
        months.append(m)
        m = m.prev()
    return list(reversed(months))


def forecast_period(
    txns: list[Txn],
    horizon_months: int = 1,
    n_lookback: int = 3,
    as_of: date | None = None,
) -> Forecast:
    if as_of is None:
        as_of = max((t.txn_date for t in txns), default=date.today())

    recurring_groups = detect_recurring(txns)
    recurring_txn_ids = {tid for g in recurring_groups for tid in g.txn_ids}
    recurring_merchants_out = {
        g.merchant for g in recurring_groups if g.typical_amount_minor < 0
    }
    recurring_merchants_in = {
        g.merchant for g in recurring_groups if g.typical_amount_minor >= 0
    }

    def is_recurring(t: Txn) -> bool:
        if t.txn_id is not None and t.txn_id in recurring_txn_ids:
            return True
        merchants = (
            recurring_merchants_in if t.amount_minor >= 0 else recurring_merchants_out
        )
        return t.merchant in merchants

    months = _trailing_months(as_of, n_lookback)

    monthly_income: list[int] = []
    monthly_variable_by_cat: dict[Category, list[int]] = {}
    for m in months:
        income = 0
        var_by_cat: dict[Category, int] = {}
        for t in txns:
            if not m.contains(t.txn_date):
                continue
            if t.amount_minor >= 0:
                income += t.amount_minor
            elif not is_recurring(t):
                var_by_cat[t.category] = var_by_cat.get(t.category, 0) - t.amount_minor
        monthly_income.append(income)
        for c in Category:
            monthly_variable_by_cat.setdefault(c, []).append(var_by_cat.get(c, 0))

    expected_income = int(median(monthly_income)) if monthly_income else 0
    by_category_variable = {
        c: int(median(vals))
        for c, vals in monthly_variable_by_cat.items()
        if vals and int(median(vals)) > 0
    }
    expected_variable = sum(by_category_variable.values())
    expected_recurring = sum(
        -g.monthly_equivalent_minor
        for g in recurring_groups
        if g.monthly_equivalent_minor < 0
    )

    return Forecast(
        expected_income_minor=expected_income,
        expected_recurring_minor=expected_recurring,
        expected_variable_minor=expected_variable,
        by_category_variable=by_category_variable,
        recurring_items=recurring_groups,
        lookback_months=n_lookback,
        as_of=as_of,
    )
