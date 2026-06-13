from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from app.engine.affordability import can_afford
from app.engine.forecast import forecast_period
from app.schemas import Forecast

AS_OF = date(2026, 4, 1)
BUFFER = 50_000_00


def test_affordability_golden_not_affordable(history):
    """250k laptop one month out on a 100k balance: projected = 100k + 138k
    surplus = 238k; after purchase −12k; 62k short of the 50k buffer."""
    f = forecast_period(history, n_lookback=3, as_of=AS_OF)
    r = can_afford(250_000_00, date(2026, 5, 1), 100_000_00, f, BUFFER, as_of=AS_OF)
    assert not r.affordable
    assert r.months_until_target == 1
    assert r.projected_balance_minor == 238_000_00
    assert r.balance_after_purchase_minor == -12_000_00
    assert r.shortfall_minor == 62_000_00


def test_affordability_golden_affordable_two_months(history):
    """Same purchase two months out: projected = 100k + 2×138k = 376k;
    after purchase 126k ≥ 50k buffer."""
    f = forecast_period(history, n_lookback=3, as_of=AS_OF)
    r = can_afford(250_000_00, date(2026, 6, 1), 100_000_00, f, BUFFER, as_of=AS_OF)
    assert r.affordable
    assert r.months_until_target == 2
    assert r.projected_balance_minor == 376_000_00
    assert r.balance_after_purchase_minor == 126_000_00
    assert r.shortfall_minor == 0


forecast_strategy = st.builds(
    Forecast,
    expected_income_minor=st.integers(min_value=0, max_value=10**9),
    expected_recurring_minor=st.integers(min_value=0, max_value=10**8),
    expected_variable_minor=st.integers(min_value=0, max_value=10**8),
    by_category_variable=st.just({}),
    lookback_months=st.just(3),
    as_of=st.just(AS_OF),
)


@given(
    forecast=forecast_strategy,
    balance=st.integers(min_value=-10**9, max_value=10**9),
    p1=st.integers(min_value=0, max_value=10**9),
    p2=st.integers(min_value=0, max_value=10**9),
    months_out=st.integers(min_value=0, max_value=24),
)
def test_affordability_is_monotonic(forecast, balance, p1, p2, months_out):
    """Raising the purchase amount never flips 'no' to 'yes'."""
    lo, hi = sorted((p1, p2))
    target = date(2026 + (4 + months_out - 1) // 12, (4 + months_out - 1) % 12 + 1, 1)
    r_lo = can_afford(lo, target, balance, forecast, BUFFER, as_of=AS_OF)
    r_hi = can_afford(hi, target, balance, forecast, BUFFER, as_of=AS_OF)
    assert not (r_hi.affordable and not r_lo.affordable)
    # Breakdown is internally consistent.
    for r, p in ((r_lo, lo), (r_hi, hi)):
        assert r.balance_after_purchase_minor == r.projected_balance_minor - p
        assert r.affordable == (r.balance_after_purchase_minor >= BUFFER)
        assert r.shortfall_minor == max(0, BUFFER - r.balance_after_purchase_minor)
