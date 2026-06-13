"""Affordability verdict with a full, explainable breakdown.

projected_balance = current_balance
                  + months * expected_income
                  - months * expected_recurring
                  - months * expected_variable
affordable  = (projected_balance - purchase) >= safety_buffer
shortfall   = max(0, safety_buffer - (projected_balance - purchase))

Monotonic by construction: raising the purchase amount can never flip a "no"
to a "yes" (property-tested).
"""
from datetime import date

from ..schemas import AffordabilityResult, Forecast, YearMonth, months_between


def can_afford(
    purchase_minor: int,
    target_date: date,
    current_balance_minor: int,
    forecast: Forecast,
    safety_buffer_minor: int,
    as_of: date | None = None,
) -> AffordabilityResult:
    if as_of is None:
        as_of = forecast.as_of
    months = max(0, months_between(YearMonth.of(as_of), YearMonth.of(target_date)))

    income_total = months * forecast.expected_income_minor
    recurring_total = months * forecast.expected_recurring_minor
    variable_total = months * forecast.expected_variable_minor

    projected = current_balance_minor + income_total - recurring_total - variable_total
    after_purchase = projected - purchase_minor
    affordable = after_purchase >= safety_buffer_minor
    shortfall = max(0, safety_buffer_minor - after_purchase)

    return AffordabilityResult(
        affordable=affordable,
        purchase_minor=purchase_minor,
        target_date=target_date,
        months_until_target=months,
        current_balance_minor=current_balance_minor,
        expected_income_total_minor=income_total,
        expected_recurring_total_minor=recurring_total,
        expected_variable_total_minor=variable_total,
        projected_balance_minor=projected,
        balance_after_purchase_minor=after_purchase,
        safety_buffer_minor=safety_buffer_minor,
        shortfall_minor=shortfall,
    )
