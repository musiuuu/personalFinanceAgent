"""Balance-integrity check: opening + sum(txns) must equal stated closing.

This is the project's strongest "the numbers are right" guarantee. A statement
that fails this check is marked failed and the agent must not silently answer
questions against it.
"""
from ..schemas import ReconcileResult, Txn


def reconcile(
    opening_balance_minor: int,
    txns: list[Txn],
    stated_closing_minor: int,
) -> ReconcileResult:
    txn_sum = sum(t.amount_minor for t in txns)
    expected_closing = opening_balance_minor + txn_sum
    discrepancy = stated_closing_minor - expected_closing
    return ReconcileResult(
        ok=discrepancy == 0,
        opening_balance_minor=opening_balance_minor,
        txn_sum_minor=txn_sum,
        expected_closing_minor=expected_closing,
        stated_closing_minor=stated_closing_minor,
        discrepancy_minor=discrepancy,
    )
