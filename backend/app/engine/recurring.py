"""Recurring-payment (subscription) detection.

A merchant group is recurring when it has >= 3 occurrences whose gaps cluster
around a known cadence (weekly 7 ±2, monthly 30 ±4, yearly 365 ±15 days) and
whose amounts are stable (within ±10% of the median).

Price changes: a subscription whose price changed is still a subscription, so
with >= 4 occurrences we also accept a series that splits into TWO stable
runs (old price, then new price) at a single changepoint; the jump (>10%
between run medians) is exactly the "your subscription got more expensive"
signal flagged as `price_change`, and the NEW price is what forecasts carry
forward. With exactly 3 occurrences all amounts must be stable — too little
history to tell a price change from ordinary variable spend (e.g. monthly
grocery runs of drifting size).
"""
import hashlib
from statistics import median

from ..schemas import RecurringGroup, Txn

CADENCES: list[tuple[int, int]] = [(7, 2), (30, 4), (365, 15)]
AMOUNT_STABILITY_PCT = 10.0
PRICE_CHANGE_PCT = 10.0
MIN_OCCURRENCES = 3


def _match_cadence(gaps: list[int]) -> int | None:
    for cadence, tol in CADENCES:
        if all(abs(g - cadence) <= tol for g in gaps):
            return cadence
    return None


def _group_id(merchant: str, cadence: int) -> str:
    return hashlib.sha256(f"{merchant}|{cadence}".encode()).hexdigest()[:12]


def _is_stable(amounts: list[int]) -> int | None:
    """Median of the run if every amount is within ±10% of it, else None."""
    med = int(median(amounts))
    if med == 0:
        return None
    tol = abs(med) * AMOUNT_STABILITY_PCT / 100
    return med if all(abs(a - med) <= tol for a in amounts) else None


def _stable_split(amounts: list[int]) -> tuple[int, int | None] | None:
    """Classify an amount series.

    Returns (median, None) for a single stable run, (old_median, new_median)
    for two stable runs separated by a >10% price change, or None when the
    series is just irregular. The changepoint path needs >= 4 points with an
    established (>= 2 point) old-price baseline.
    """
    whole = _is_stable(amounts)
    if whole is not None:
        return whole, None
    if len(amounts) < 4:
        return None
    for k in range(2, len(amounts)):  # suffix may be a single occurrence
        old = _is_stable(amounts[:k])
        new = _is_stable(amounts[k:])
        if old is None or new is None:
            continue
        if abs(new - old) > abs(old) * PRICE_CHANGE_PCT / 100:
            return old, new
    return None


def detect_recurring(txns: list[Txn]) -> list[RecurringGroup]:
    by_merchant: dict[str, list[Txn]] = {}
    for t in txns:
        if t.merchant:
            by_merchant.setdefault(t.merchant, []).append(t)

    groups: list[RecurringGroup] = []
    for merchant, items in by_merchant.items():
        # Inflows and outflows are separate phenomena (salary vs subscription).
        for sign in (1, -1):
            series = sorted(
                (t for t in items if (t.amount_minor >= 0) == (sign > 0)),
                key=lambda t: t.txn_date,
            )
            if len(series) < MIN_OCCURRENCES:
                continue

            gaps = [
                (series[i + 1].txn_date - series[i].txn_date).days
                for i in range(len(series) - 1)
            ]
            cadence = _match_cadence(gaps)
            if cadence is None:
                continue

            amounts = [t.amount_minor for t in series]
            split = _stable_split(amounts)
            if split is None:
                continue
            old_med, new_med = split
            if new_med is None:
                typical = old_med
                go_forward = old_med
                price_change = False
                change_pct = None
            else:
                typical = old_med
                go_forward = new_med
                price_change = True
                change_pct = round(
                    (abs(new_med) - abs(old_med)) / abs(old_med) * 100, 1
                )

            groups.append(
                RecurringGroup(
                    group_id=_group_id(merchant, cadence),
                    merchant=merchant,
                    cadence_days=cadence,
                    typical_amount_minor=typical,
                    occurrences=len(series),
                    first_date=series[0].txn_date,
                    last_date=series[-1].txn_date,
                    monthly_equivalent_minor=round(go_forward * 30 / cadence),
                    price_change=price_change,
                    price_change_pct=change_pct,
                    last_amount_minor=amounts[-1],
                    txn_ids=[t.txn_id for t in series if t.txn_id is not None],
                )
            )

    groups.sort(key=lambda g: abs(g.monthly_equivalent_minor), reverse=True)
    return groups
