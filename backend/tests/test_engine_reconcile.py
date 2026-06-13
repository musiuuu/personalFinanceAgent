from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from app.engine.reconcile import reconcile
from app.models import Category
from app.schemas import Txn


def _txn(amount_minor: int) -> Txn:
    return Txn(
        txn_date=date(2026, 1, 15),
        amount_minor=amount_minor,
        category=Category.OTHER,
        raw_description="x",
    )


def test_reconcile_ok_golden():
    txns = [_txn(250_000_00), _txn(-60_000_00), _txn(-2_000_00)]
    r = reconcile(100_000_00, txns, 288_000_00)
    assert r.ok
    assert r.expected_closing_minor == 288_000_00
    assert r.discrepancy_minor == 0


def test_reconcile_discrepancy_golden():
    txns = [_txn(250_000_00), _txn(-60_000_00)]
    r = reconcile(100_000_00, txns, 285_000_00)  # statement claims 285k
    assert not r.ok
    assert r.expected_closing_minor == 290_000_00
    assert r.discrepancy_minor == -5_000_00  # stated - expected


@given(
    opening=st.integers(min_value=-10**12, max_value=10**12),
    amounts=st.lists(
        st.integers(min_value=-10**9, max_value=10**9), max_size=200
    ),
    noise=st.integers(min_value=-10**6, max_value=10**6),
)
def test_reconcile_property(opening, amounts, noise):
    txns = [_txn(a) for a in amounts]
    true_closing = opening + sum(amounts)
    r = reconcile(opening, txns, true_closing + noise)
    assert r.expected_closing_minor == true_closing
    assert r.ok == (noise == 0)
    assert r.discrepancy_minor == noise
