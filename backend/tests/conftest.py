"""Shared fixtures: a hand-built transaction history with known truth.

Three months (Jan–Mar 2026) of synthetic PKR data. Every golden number in the
engine tests below was computed by hand from this table — if an engine change
breaks a golden test, the engine is wrong, not the test.
"""
from datetime import date

import pytest

from app.models import Category
from app.schemas import Txn


def T(y, m, d, amount_pkr, category, merchant=None, desc="", txn_id=None):
    return Txn(
        txn_date=date(y, m, d),
        amount_minor=amount_pkr * 100,
        category=category,
        merchant=merchant,
        raw_description=desc or (merchant or "txn"),
        txn_id=txn_id,
    )


@pytest.fixture
def history() -> list[Txn]:
    """Jan–Mar 2026.

    Recurring: ACME salary +250,000/mo (1st), Netflix -2,000/mo (5th),
    rent -60,000/mo (3rd).
    Variable: groceries 30k/35k/40k (median 35k), dining 10k/8k/12k
    (median 10k), transport 5k/5k/6k (median 5k).
    """
    txns = []
    i = 1
    months = [(2026, 1), (2026, 2), (2026, 3)]
    groceries = [30_000, 35_000, 40_000]
    dining = [10_000, 8_000, 12_000]
    transport = [5_000, 5_000, 6_000]
    for idx, (y, m) in enumerate(months):
        txns += [
            T(y, m, 1, 250_000, Category.SALARY, "ACME CORP", "SALARY ACME", txn_id=i),
            T(y, m, 3, -60_000, Category.RENT, "LANDLORD", "RENT TRANSFER", txn_id=i + 1),
            T(y, m, 5, -2_000, Category.SUBSCRIPTIONS, "NETFLIX", "NETFLIX.COM", txn_id=i + 2),
            T(y, m, 10, -groceries[idx], Category.GROCERIES, "IMTIAZ", "IMTIAZ SUPER MARKET", txn_id=i + 3),
            T(y, m, 15, -dining[idx], Category.DINING, "FOODPANDA", "FOODPANDA ORDER", txn_id=i + 4),
            T(y, m, 20, -transport[idx], Category.TRANSPORT, "CAREEM", "CAREEM RIDE", txn_id=i + 5),
        ]
        i += 6
    return txns
