"""Savings planning: honest feasibility, month-by-month schedule.

If the required monthly saving exceeds the forecast surplus the plan is
returned as infeasible with the exact gap and a ranked list of variable
category cuts that would close it. No fabricated optimism.
"""
from ..schemas import Forecast, SavingsMonth, SavingsPlan, SuggestedCut


def savings_plan(
    goal_minor: int,
    horizon_months: int,
    current_balance_minor: int,
    forecast: Forecast,
    already_saved_minor: int = 0,
) -> SavingsPlan:
    if horizon_months <= 0:
        raise ValueError("horizon_months must be >= 1")

    remaining = max(0, goal_minor - already_saved_minor)
    surplus = forecast.expected_surplus_minor
    required_monthly = -(-remaining // horizon_months)  # ceil division
    feasible = required_monthly <= surplus
    gap = max(0, required_monthly - surplus)

    # Ranked cuts: largest variable categories first, capped at what each
    # category actually spends, until the gap is closed.
    suggested_cuts: list[SuggestedCut] = []
    if not feasible:
        to_close = gap
        for cat, monthly in sorted(
            forecast.by_category_variable.items(), key=lambda kv: kv[1], reverse=True
        ):
            if to_close <= 0:
                break
            cut = min(monthly, to_close)
            if cut <= 0:
                continue
            suggested_cuts.append(
                SuggestedCut(
                    category=cat,
                    current_monthly_minor=monthly,
                    suggested_cut_minor=cut,
                )
            )
            to_close -= cut

    # Month-by-month schedule. Equal installments with the remainder folded
    # into the final month so the schedule sums to the goal exactly.
    schedule: list[SavingsMonth] = []
    base = remaining // horizon_months
    leftover = remaining - base * horizon_months
    cumulative = 0
    balance = current_balance_minor
    for i in range(1, horizon_months + 1):
        save = base + (leftover if i == horizon_months else 0)
        cumulative += save
        balance += surplus  # surplus accrues whether or not it covers `save`
        schedule.append(
            SavingsMonth(
                month_index=i,
                save_minor=save,
                cumulative_saved_minor=cumulative,
                projected_balance_minor=balance,
            )
        )

    return SavingsPlan(
        feasible=feasible,
        goal_minor=goal_minor,
        already_saved_minor=already_saved_minor,
        horizon_months=horizon_months,
        required_monthly_minor=required_monthly,
        monthly_surplus_minor=surplus,
        gap_minor=gap,
        suggested_cuts=suggested_cuts,
        schedule=schedule,
    )
