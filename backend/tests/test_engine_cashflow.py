from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from app.engine.cashflow import cashflow_delta, monthly_cashflow
from app.models import Category
from app.schemas import Txn, YearMonth

# ------------------------------------------------------------------- golden
# Hand-computed from conftest.history (Jan 2026):
# income = 250,000; expense = 60,000+2,000+30,000+10,000+5,000 = 107,000
# net = 143,000; six transactions.


def test_monthly_cashflow_golden_january(history):
    r = monthly_cashflow(history, YearMonth(year=2026, month=1))
    assert r.income_minor == 250_000_00
    assert r.expense_minor == 107_000_00
    assert r.net_minor == 143_000_00
    assert r.txn_count == 6
    assert r.by_category[Category.RENT] == 60_000_00
    assert r.by_category[Category.GROCERIES] == 30_000_00
    assert r.by_category[Category.DINING] == 10_000_00
    assert r.by_category[Category.TRANSPORT] == 5_000_00
    assert r.by_category[Category.SUBSCRIPTIONS] == 2_000_00
    assert r.income_by_category[Category.SALARY] == 250_000_00


def test_cashflow_delta_golden_jan_to_march(history):
    d = cashflow_delta(
        history, YearMonth(year=2026, month=1), YearMonth(year=2026, month=3)
    )
    # March expense = 60k+2k+40k+12k+6k = 120,000 → net 130,000
    assert d.net_a_minor == 143_000_00
    assert d.net_b_minor == 130_000_00
    assert d.net_delta_minor == -13_000_00
    assert d.income_delta_minor == 0
    assert d.expense_delta_minor == 13_000_00
    # Ranked by impact: groceries +10k, dining +2k, transport +1k
    top = d.category_deltas[0]
    assert top.category == Category.GROCERIES
    assert top.delta_minor == 10_000_00


def test_empty_month_is_all_zero(history):
    r = monthly_cashflow(history, YearMonth(year=2025, month=6))
    assert r.income_minor == r.expense_minor == r.net_minor == r.txn_count == 0
    assert r.by_category == {}


# ---------------------------------------------------------------- properties

txn_strategy = st.builds(
    Txn,
    txn_date=st.dates(min_value=date(2025, 1, 1), max_value=date(2026, 12, 31)),
    amount_minor=st.integers(min_value=-10_000_000_00, max_value=10_000_000_00),
    category=st.sampled_from(list(Category)),
    merchant=st.one_of(st.none(), st.text(min_size=1, max_size=12)),
)


@given(st.lists(txn_strategy, max_size=60))
def test_by_category_sums_to_total_expense(txns):
    for month in {YearMonth.of(t.txn_date) for t in txns}:
        r = monthly_cashflow(txns, month)
        assert sum(r.by_category.values()) == r.expense_minor
        assert sum(r.income_by_category.values()) == r.income_minor
        assert r.net_minor == r.income_minor - r.expense_minor
        assert r.expense_minor >= 0 and r.income_minor >= 0


@given(st.lists(txn_strategy, max_size=60))
def test_months_partition_the_ledger(txns):
    months = {YearMonth.of(t.txn_date) for t in txns}
    total_net = sum(monthly_cashflow(txns, m).net_minor for m in months)
    assert total_net == sum(t.amount_minor for t in txns)
