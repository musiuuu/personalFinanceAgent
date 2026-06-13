"""What-if simulation: apply scenario deltas to the forecast and project
before-vs-after balances month by month.
"""
from datetime import date

from ..schemas import Forecast, ScenarioDelta, SimMonth, SimResult, Txn
from .forecast import forecast_period


def _apply(forecast: Forecast, deltas: list[ScenarioDelta]) -> tuple[Forecast, list[str]]:
    """Return an adjusted copy of the forecast plus human-readable notes."""
    income = forecast.expected_income_minor
    recurring = forecast.expected_recurring_minor
    by_cat = dict(forecast.by_category_variable)
    notes: list[str] = []

    for d in deltas:
        if d.type == "cut_category":
            current = by_cat.get(d.category, 0)
            cut = round(current * d.pct / 100)
            by_cat[d.category] = current - cut
            notes.append(f"Cut {d.category.value} by {d.pct:.0f}% (-{cut} minor/month)")
        elif d.type == "cancel":
            target = d.merchant.strip().upper()
            matched = [
                g
                for g in forecast.recurring_items
                if g.monthly_equivalent_minor < 0 and target in g.merchant.upper()
            ]
            if not matched:
                notes.append(f"No recurring charge found for '{d.merchant}' — nothing cancelled")
            for g in matched:
                recurring += g.monthly_equivalent_minor  # equivalents are negative
                notes.append(
                    f"Cancelled {g.merchant} (+{-g.monthly_equivalent_minor} minor/month)"
                )
        elif d.type == "add_expense":
            amount = abs(d.amount_minor)
            if d.recurring:
                recurring += amount
                notes.append(f"Added recurring expense of {amount} minor/month")
            else:
                # One-time expense is modeled as a first-month-only outflow via
                # the one_time list handled by the caller.
                notes.append(f"Added one-time expense of {amount} minor in month 1")
        elif d.type == "income_change":
            income += d.amount_minor
            sign = "+" if d.amount_minor >= 0 else ""
            notes.append(f"Income change {sign}{d.amount_minor} minor/month")

    adjusted = forecast.model_copy(
        update={
            "expected_income_minor": income,
            "expected_recurring_minor": recurring,
            "expected_variable_minor": sum(by_cat.values()),
            "by_category_variable": by_cat,
        }
    )
    return adjusted, notes


def simulate(
    txns: list[Txn],
    scenario: list[ScenarioDelta],
    horizon_months: int,
    current_balance_minor: int = 0,
    as_of: date | None = None,
    n_lookback: int = 3,
) -> SimResult:
    baseline = forecast_period(txns, horizon_months, n_lookback=n_lookback, as_of=as_of)
    adjusted, notes = _apply(baseline, scenario)

    one_time = sum(
        abs(d.amount_minor)
        for d in scenario
        if d.type == "add_expense" and not d.recurring
    )

    base_net = baseline.expected_surplus_minor
    scen_net = adjusted.expected_surplus_minor

    months: list[SimMonth] = []
    bal_before = current_balance_minor
    bal_after = current_balance_minor
    for i in range(1, horizon_months + 1):
        bal_before += base_net
        bal_after += scen_net - (one_time if i == 1 else 0)
        months.append(
            SimMonth(
                month_index=i,
                balance_before_minor=bal_before,
                balance_after_minor=bal_after,
                delta_minor=bal_after - bal_before,
            )
        )

    return SimResult(
        horizon_months=horizon_months,
        baseline_monthly_net_minor=base_net,
        scenario_monthly_net_minor=scen_net,
        monthly_impact_minor=scen_net - base_net,
        months=months,
        applied=scenario,
        notes=notes,
    )
