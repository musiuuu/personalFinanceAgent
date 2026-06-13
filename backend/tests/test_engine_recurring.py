from datetime import date

from app.engine.recurring import detect_recurring
from app.models import Category
from app.schemas import Txn


def _series(merchant, amounts_pkr, dates, category=Category.SUBSCRIPTIONS):
    return [
        Txn(
            txn_date=d,
            amount_minor=a * 100,
            category=category,
            merchant=merchant,
            raw_description=merchant,
            txn_id=i + 1,
        )
        for i, (a, d) in enumerate(zip(amounts_pkr, dates))
    ]


MONTHLY_DATES = [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)]


def test_detects_monthly_subscription(history):
    groups = {g.merchant: g for g in detect_recurring(history)}
    assert "NETFLIX" in groups
    g = groups["NETFLIX"]
    assert g.cadence_days == 30
    assert g.typical_amount_minor == -2_000_00
    assert g.monthly_equivalent_minor == -2_000_00
    assert not g.price_change


def test_salary_detected_as_recurring_inflow(history):
    groups = {g.merchant: g for g in detect_recurring(history)}
    assert groups["ACME CORP"].typical_amount_minor == 250_000_00


def test_variable_spend_not_recurring(history):
    """Groceries/dining/transport vary >10% — must not be subscriptions."""
    merchants = {g.merchant for g in detect_recurring(history)}
    assert merchants == {"ACME CORP", "LANDLORD", "NETFLIX"}


def test_two_occurrences_not_enough():
    txns = _series("SPOTIFY", [-500, -500], MONTHLY_DATES[:2])
    assert detect_recurring(txns) == []


def test_irregular_cadence_rejected():
    dates = [date(2026, 1, 5), date(2026, 1, 20), date(2026, 3, 1)]
    txns = _series("RANDOM SHOP", [-1000, -1000, -1000], dates)
    assert detect_recurring(txns) == []


def test_price_change_flagged_with_four_occurrences():
    txns = _series("NETFLIX", [-2000, -2000, -2000, -2600], MONTHLY_DATES)
    groups = detect_recurring(txns)
    assert len(groups) == 1
    g = groups[0]
    assert g.price_change
    assert g.price_change_pct == 30.0
    assert g.typical_amount_minor == -2_000_00
    assert g.last_amount_minor == -2_600_00
    # Forecast should carry the NEW price forward.
    assert g.monthly_equivalent_minor == -2_600_00


def test_no_price_change_within_tolerance():
    txns = _series("NETFLIX", [-2000, -2000, -2000, -2100], MONTHLY_DATES)
    g = detect_recurring(txns)[0]
    assert not g.price_change  # 5% drift is within the ±10% band


def test_weekly_cadence():
    dates = [date(2026, 3, 2), date(2026, 3, 9), date(2026, 3, 16), date(2026, 3, 23)]
    txns = _series("GYM", [-1500, -1500, -1500, -1500], dates)
    g = detect_recurring(txns)[0]
    assert g.cadence_days == 7
    assert g.monthly_equivalent_minor == round(-1500_00 * 30 / 7)
