from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from app.engine.forecast import forecast_period
from app.engine.savings_plan import savings_plan
from app.models import Category
from app.schemas import Forecast

AS_OF = date(2026, 4, 1)


def test_savings_plan_golden_feasible(history):
    """300k over 3 months needs 100k/month against a 138k surplus."""
    f = forecast_period(history, n_lookback=3, as_of=AS_OF)
    p = savings_plan(300_000_00, 3, 100_000_00, f)
    assert p.feasible
    assert p.required_monthly_minor == 100_000_00
    assert p.monthly_surplus_minor == 138_000_00
    assert p.gap_minor == 0
    assert p.suggested_cuts == []
    assert [m.save_minor for m in p.schedule] == [100_000_00] * 3
    assert p.schedule[-1].cumulative_saved_minor == 300_000_00
    # Balance projection: 100k + n×138k
    assert [m.projected_balance_minor for m in p.schedule] == [
        238_000_00,
        376_000_00,
        514_000_00,
    ]


def test_savings_plan_golden_infeasible_with_ranked_cuts(history):
    """600k over 3 months needs 200k/month; surplus is 138k → gap 62k.
    Ranked cuts: groceries 35k, dining 10k, transport 5k (50k total —
    honestly insufficient, and reported as such)."""
    f = forecast_period(history, n_lookback=3, as_of=AS_OF)
    p = savings_plan(600_000_00, 3, 100_000_00, f)
    assert not p.feasible
    assert p.required_monthly_minor == 200_000_00
    assert p.gap_minor == 62_000_00
    cuts = [(c.category, c.suggested_cut_minor) for c in p.suggested_cuts]
    assert cuts == [
        (Category.GROCERIES, 35_000_00),
        (Category.DINING, 10_000_00),
        (Category.TRANSPORT, 5_000_00),
    ]


def test_savings_plan_respects_already_saved(history):
    f = forecast_period(history, n_lookback=3, as_of=AS_OF)
    p = savings_plan(300_000_00, 3, 0, f, already_saved_minor=150_000_00)
    assert p.required_monthly_minor == 50_000_00
    assert p.schedule[-1].cumulative_saved_minor == 150_000_00


@given(
    goal=st.integers(min_value=0, max_value=10**9),
    horizon=st.integers(min_value=1, max_value=60),
    saved=st.integers(min_value=0, max_value=10**9),
    surplus=st.integers(min_value=-10**7, max_value=10**8),
)
def test_schedule_always_sums_to_remaining_goal(goal, horizon, saved, surplus):
    f = Forecast(
        expected_income_minor=max(surplus, 0),
        expected_recurring_minor=max(-surplus, 0),
        expected_variable_minor=0,
        by_category_variable={},
        lookback_months=3,
        as_of=AS_OF,
    )
    p = savings_plan(goal, horizon, 0, f, already_saved_minor=saved)
    remaining = max(0, goal - saved)
    assert p.schedule[-1].cumulative_saved_minor == remaining
    assert sum(m.save_minor for m in p.schedule) == remaining
    assert all(m.save_minor >= 0 for m in p.schedule)
    assert len(p.schedule) == horizon
    # Feasibility is exactly "required <= surplus".
    assert p.feasible == (p.required_monthly_minor <= p.monthly_surplus_minor)
