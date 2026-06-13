"""Anomaly detection — four independent rules, each with a readable reason.

1. Robust outlier: |amount| beyond median ± k·MAD within its category
   (MAD = median absolute deviation; robust to skew, unlike mean/std).
2. New large merchant: first-ever charge to a merchant AND above the 90th
   percentile of all outflow magnitudes.
3. Duplicate charge: same merchant + same amount within 48 hours.
4. Recurring price spike: a recurring group whose latest amount jumped >10%.
"""
from statistics import median

from ..schemas import Anomaly, RecurringGroup, Txn
from .recurring import detect_recurring

MIN_CATEGORY_SAMPLE = 5
NEW_MERCHANT_PERCENTILE = 0.90
DUPLICATE_WINDOW_HOURS = 48


def _fmt_pkr(minor: int) -> str:
    return f"PKR {abs(minor) / 100:,.0f}"


def _percentile(sorted_vals: list[int], q: float) -> int:
    if not sorted_vals:
        return 0
    idx = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[idx]


def detect_anomalies(
    txns: list[Txn],
    mad_k: float = 3.5,
    recurring_groups: list[RecurringGroup] | None = None,
) -> list[Anomaly]:
    if recurring_groups is None:
        recurring_groups = detect_recurring(txns)

    outflows = [t for t in txns if t.amount_minor < 0]
    anomalies: list[Anomaly] = []
    flagged: set[tuple[int | None, str]] = set()

    def add(t: Txn, kind: str, reason: str) -> None:
        key = (t.txn_id, kind)
        if key in flagged:
            return
        flagged.add(key)
        anomalies.append(
            Anomaly(
                txn_id=t.txn_id,
                txn_date=t.txn_date,
                merchant=t.merchant,
                amount_minor=t.amount_minor,
                category=t.category,
                kind=kind,
                reason=reason,
            )
        )

    # Rule 1 — robust outlier within category
    by_cat: dict[str, list[Txn]] = {}
    for t in outflows:
        by_cat.setdefault(t.category.value, []).append(t)
    for cat, items in by_cat.items():
        if len(items) < MIN_CATEGORY_SAMPLE:
            continue
        magnitudes = [-t.amount_minor for t in items]
        med = median(magnitudes)
        mad = median([abs(m - med) for m in magnitudes])
        if mad == 0:
            continue  # degenerate: all-identical amounts; rule 3/4 cover dupes
        for t in items:
            mag = -t.amount_minor
            if abs(mag - med) > mad_k * mad:
                add(
                    t,
                    "robust_outlier",
                    f"{_fmt_pkr(t.amount_minor)} is far outside the typical "
                    f"{cat} spend of {_fmt_pkr(int(med))} "
                    f"(beyond {mad_k}×MAD).",
                )

    # Rule 2 — first-ever merchant charge that is also large
    sorted_mags = sorted(-t.amount_minor for t in outflows)
    p90 = _percentile(sorted_mags, NEW_MERCHANT_PERCENTILE)
    seen_merchants: set[str] = set()
    for t in sorted(outflows, key=lambda x: x.txn_date):
        if not t.merchant:
            continue
        if t.merchant not in seen_merchants and -t.amount_minor > p90:
            add(
                t,
                "new_large_merchant",
                f"First charge ever to {t.merchant} and it is "
                f"{_fmt_pkr(t.amount_minor)} — above the 90th percentile "
                f"of your outflows.",
            )
        seen_merchants.add(t.merchant)

    # Rule 3 — duplicate charge within 48h
    by_pair: dict[tuple[str, int], list[Txn]] = {}
    for t in outflows:
        if t.merchant:
            by_pair.setdefault((t.merchant, t.amount_minor), []).append(t)
    for (merchant, _amount), items in by_pair.items():
        items.sort(key=lambda x: x.txn_date)
        for a, b in zip(items, items[1:]):
            if (b.txn_date - a.txn_date).days * 24 <= DUPLICATE_WINDOW_HOURS:
                add(
                    b,
                    "duplicate_charge",
                    f"Possible duplicate: {merchant} charged "
                    f"{_fmt_pkr(b.amount_minor)} twice within 48 hours.",
                )

    # Rule 4 — recurring price spike
    txn_by_id = {t.txn_id: t for t in txns if t.txn_id is not None}
    for g in recurring_groups:
        if not g.price_change or g.monthly_equivalent_minor >= 0:
            continue
        last_txn = txn_by_id.get(g.txn_ids[-1]) if g.txn_ids else None
        if last_txn is None:
            candidates = [
                t for t in outflows
                if t.merchant == g.merchant and t.txn_date == g.last_date
            ]
            last_txn = candidates[-1] if candidates else None
        if last_txn is not None:
            direction = "increased" if (g.price_change_pct or 0) > 0 else "decreased"
            add(
                last_txn,
                "recurring_price_spike",
                f"Your recurring {g.merchant} payment {direction} by "
                f"{abs(g.price_change_pct or 0):.1f}% "
                f"(now {_fmt_pkr(g.last_amount_minor or 0)}, was "
                f"{_fmt_pkr(g.typical_amount_minor)}).",
            )

    anomalies.sort(key=lambda a: a.txn_date, reverse=True)
    return anomalies
