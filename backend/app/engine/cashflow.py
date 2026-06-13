"""Monthly cashflow aggregation and month-over-month diagnosis.

Pure functions only: no I/O, no LLM, no globals.
"""
from ..models import Category
from ..schemas import CashflowDelta, CashflowResult, CategoryDelta, Txn, YearMonth


def monthly_cashflow(txns: list[Txn], month: YearMonth) -> CashflowResult:
    income = 0
    expense = 0
    by_category: dict[Category, int] = {}
    income_by_category: dict[Category, int] = {}
    count = 0

    for t in txns:
        if not month.contains(t.txn_date):
            continue
        count += 1
        if t.amount_minor >= 0:
            income += t.amount_minor
            income_by_category[t.category] = (
                income_by_category.get(t.category, 0) + t.amount_minor
            )
        else:
            magnitude = -t.amount_minor
            expense += magnitude
            by_category[t.category] = by_category.get(t.category, 0) + magnitude

    return CashflowResult(
        month=month,
        income_minor=income,
        expense_minor=expense,
        net_minor=income - expense,
        by_category=by_category,
        income_by_category=income_by_category,
        txn_count=count,
    )


def cashflow_delta(txns: list[Txn], month_a: YearMonth, month_b: YearMonth) -> CashflowDelta:
    """Explain why cashflow changed between two months, ranked by impact."""
    a = monthly_cashflow(txns, month_a)
    b = monthly_cashflow(txns, month_b)

    categories = set(a.by_category) | set(b.by_category)
    deltas = [
        CategoryDelta(
            category=c,
            amount_a_minor=a.by_category.get(c, 0),
            amount_b_minor=b.by_category.get(c, 0),
            delta_minor=b.by_category.get(c, 0) - a.by_category.get(c, 0),
        )
        for c in categories
    ]
    deltas.sort(key=lambda d: abs(d.delta_minor), reverse=True)

    return CashflowDelta(
        month_a=month_a,
        month_b=month_b,
        net_a_minor=a.net_minor,
        net_b_minor=b.net_minor,
        net_delta_minor=b.net_minor - a.net_minor,
        income_delta_minor=b.income_minor - a.income_minor,
        expense_delta_minor=b.expense_minor - a.expense_minor,
        category_deltas=deltas,
    )
