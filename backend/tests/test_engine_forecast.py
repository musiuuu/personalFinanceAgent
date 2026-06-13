from datetime import date

from app.engine.forecast import forecast_period
from app.models import Category

AS_OF = date(2026, 4, 1)  # lookback window = Jan, Feb, Mar 2026

# Hand-computed from conftest.history:
#   recurring outflows: rent 60,000 + Netflix 2,000 = 62,000 / month
#   variable medians:   groceries 35,000, dining 10,000, transport 5,000 → 50,000
#   income median:      250,000


def test_forecast_golden(history):
    f = forecast_period(history, horizon_months=1, n_lookback=3, as_of=AS_OF)
    assert f.expected_income_minor == 250_000_00
    assert f.expected_recurring_minor == 62_000_00
    assert f.expected_variable_minor == 50_000_00
    assert f.by_category_variable[Category.GROCERIES] == 35_000_00
    assert f.by_category_variable[Category.DINING] == 10_000_00
    assert f.by_category_variable[Category.TRANSPORT] == 5_000_00
    assert f.expected_surplus_minor == 138_000_00


def test_forecast_separates_recurring_from_variable(history):
    f = forecast_period(history, horizon_months=1, n_lookback=3, as_of=AS_OF)
    # Rent and Netflix are recurring, so they must NOT appear in variable.
    assert Category.RENT not in f.by_category_variable
    assert Category.SUBSCRIPTIONS not in f.by_category_variable
    recurring_merchants = {g.merchant for g in f.recurring_items}
    assert {"LANDLORD", "NETFLIX", "ACME CORP"} <= recurring_merchants


def test_forecast_empty_history():
    f = forecast_period([], horizon_months=1, n_lookback=3, as_of=AS_OF)
    assert f.expected_income_minor == 0
    assert f.expected_recurring_minor == 0
    assert f.expected_variable_minor == 0
