from datetime import date

from app.engine.anomalies import detect_anomalies
from app.models import Category
from app.schemas import Txn

_id = 0


def T(y, m, d, amount_pkr, category=Category.OTHER, merchant=None):
    global _id
    _id += 1
    return Txn(
        txn_date=date(y, m, d),
        amount_minor=amount_pkr * 100,
        category=category,
        merchant=merchant,
        raw_description=merchant or "txn",
        txn_id=_id,
    )


def _kinds(anomalies):
    return {(a.kind, a.txn_id) for a in anomalies}


def test_robust_outlier_in_category():
    txns = [
        T(2026, 3, i + 1, -amount, Category.DINING, f"CAFE{i}")
        for i, amount in enumerate([900, 1000, 1100, 1000, 950])
    ]
    spike = T(2026, 3, 20, -25_000, Category.DINING, "FANCY STEAKHOUSE")
    found = detect_anomalies(txns + [spike])
    assert ("robust_outlier", spike.txn_id) in _kinds(found)
    # The ordinary transactions are not flagged as outliers.
    ordinary_ids = {t.txn_id for t in txns}
    assert not any(
        a.kind == "robust_outlier" and a.txn_id in ordinary_ids for a in found
    )


def test_new_large_merchant():
    background = [
        T(2026, 3, i % 28 + 1, -500, Category.GROCERIES, "IMTIAZ") for i in range(15)
    ]
    big_new = T(2026, 3, 29, -80_000, Category.SHOPPING, "GOLD SOUK")
    found = detect_anomalies(background + [big_new])
    assert ("new_large_merchant", big_new.txn_id) in _kinds(found)


def test_duplicate_charge_within_48h():
    a = T(2026, 3, 10, -4_500, Category.DINING, "FOODPANDA")
    b = T(2026, 3, 11, -4_500, Category.DINING, "FOODPANDA")
    found = detect_anomalies([a, b])
    assert ("duplicate_charge", b.txn_id) in _kinds(found)


def test_same_amount_far_apart_not_duplicate():
    a = T(2026, 1, 10, -4_500, Category.DINING, "FOODPANDA")
    b = T(2026, 3, 11, -4_500, Category.DINING, "FOODPANDA")
    found = detect_anomalies([a, b])
    assert not any(x.kind == "duplicate_charge" for x in found)


def test_recurring_price_spike_surfaces_as_anomaly():
    dates = [date(2026, 1, 5), date(2026, 2, 5), date(2026, 3, 5), date(2026, 4, 5)]
    txns = [
        T(d.year, d.month, d.day, -2000 if i < 3 else -2600,
          Category.SUBSCRIPTIONS, "NETFLIX")
        for i, d in enumerate(dates)
    ]
    found = detect_anomalies(txns)
    spikes = [a for a in found if a.kind == "recurring_price_spike"]
    assert len(spikes) == 1
    assert spikes[0].txn_id == txns[-1].txn_id
    assert "30.0%" in spikes[0].reason


def test_every_anomaly_has_readable_reason():
    txns = [
        T(2026, 3, i + 1, -a, Category.DINING, f"C{i}")
        for i, a in enumerate([900, 1000, 1100, 1000, 950])
    ] + [T(2026, 3, 20, -25_000, Category.DINING, "SPIKE")]
    for a in detect_anomalies(txns):
        assert a.reason and len(a.reason) > 20
