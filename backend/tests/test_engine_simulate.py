from datetime import date

from app.engine.simulate import simulate
from app.models import Category
from app.schemas import ScenarioDelta

AS_OF = date(2026, 4, 1)
BALANCE = 100_000_00

# Baseline (from conftest.history): surplus = 138,000/month.


def test_cut_dining_30pct(history):
    """Dining variable is 10k/month → 30% cut saves 3k/month."""
    r = simulate(
        history,
        [ScenarioDelta(type="cut_category", category=Category.DINING, pct=30)],
        horizon_months=3,
        current_balance_minor=BALANCE,
        as_of=AS_OF,
    )
    assert r.baseline_monthly_net_minor == 138_000_00
    assert r.scenario_monthly_net_minor == 141_000_00
    assert r.monthly_impact_minor == 3_000_00
    assert r.months[-1].balance_before_minor == BALANCE + 3 * 138_000_00
    assert r.months[-1].balance_after_minor == BALANCE + 3 * 141_000_00
    assert r.months[-1].delta_minor == 9_000_00


def test_cancel_subscription(history):
    r = simulate(
        history,
        [ScenarioDelta(type="cancel", merchant="Netflix")],
        horizon_months=2,
        current_balance_minor=BALANCE,
        as_of=AS_OF,
    )
    assert r.monthly_impact_minor == 2_000_00
    assert any("NETFLIX" in n for n in r.notes)


def test_cancel_unknown_merchant_is_honest(history):
    r = simulate(
        history,
        [ScenarioDelta(type="cancel", merchant="Disney+")],
        horizon_months=1,
        current_balance_minor=BALANCE,
        as_of=AS_OF,
    )
    assert r.monthly_impact_minor == 0
    assert any("nothing cancelled" in n for n in r.notes)


def test_combined_scenario(history):
    """Cut dining 30% (+3k) and add a 10k/month expense → net −7k/month."""
    r = simulate(
        history,
        [
            ScenarioDelta(type="cut_category", category=Category.DINING, pct=30),
            ScenarioDelta(type="add_expense", amount_minor=10_000_00, recurring=True),
        ],
        horizon_months=2,
        current_balance_minor=BALANCE,
        as_of=AS_OF,
    )
    assert r.monthly_impact_minor == -7_000_00


def test_one_time_expense_hits_month_one_only(history):
    r = simulate(
        history,
        [ScenarioDelta(type="add_expense", amount_minor=50_000_00, recurring=False)],
        horizon_months=3,
        current_balance_minor=BALANCE,
        as_of=AS_OF,
    )
    assert r.months[0].delta_minor == -50_000_00
    assert r.months[2].delta_minor == -50_000_00  # gap persists, doesn't grow


def test_income_change(history):
    r = simulate(
        history,
        [ScenarioDelta(type="income_change", amount_minor=20_000_00)],
        horizon_months=1,
        current_balance_minor=BALANCE,
        as_of=AS_OF,
    )
    assert r.monthly_impact_minor == 20_000_00
