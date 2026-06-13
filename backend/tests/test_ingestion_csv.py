from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.ingestion.csv_parser import parse_csv
from app.ingestion.router import ingest_file
from app.models import Category, Transaction

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")  # in-memory
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# ----------------------------------------------------------------- adapters


def test_hbl_adapter_round_trip(session):
    result = ingest_file(session, FIXTURES / "hbl_jan2026.csv")
    assert result.bank_hint == "hbl"
    assert result.txn_count == 4
    assert result.reconciled is True
    assert result.status == "reconciled"

    txns = session.exec(select(Transaction).order_by(Transaction.txn_date)).all()
    assert [t.amount_minor for t in txns] == [
        250_000_00, -60_000_00, -2_000_00, -30_000_00
    ]
    # Rule-based categories applied during ingestion.
    assert txns[0].category == Category.SALARY.value
    assert txns[1].category == Category.RENT.value
    assert txns[2].category == Category.SUBSCRIPTIONS.value
    assert txns[3].category == Category.GROCERIES.value
    # Merchant noise (POS/REF ids) stripped.
    assert txns[2].merchant_normalized == "NETFLIX"
    assert txns[3].merchant_normalized == "IMTIAZ"


def test_meezan_adapter_round_trip(session):
    result = ingest_file(session, FIXTURES / "meezan_feb2026.csv")
    assert result.bank_hint == "meezan"
    assert result.txn_count == 3
    assert result.reconciled is True
    txns = session.exec(select(Transaction).order_by(Transaction.txn_date)).all()
    assert [t.amount_minor for t in txns] == [250_000_00, -4_500_00, -1_500_00]


def test_generic_adapter_signed_amounts(session):
    result = ingest_file(session, FIXTURES / "generic_signed.csv")
    assert result.bank_hint == "generic"
    assert result.txn_count == 3
    assert result.reconciled is True  # opening/closing inferred from balance column
    txns = session.exec(select(Transaction).order_by(Transaction.txn_date)).all()
    assert [t.amount_minor for t in txns] == [250_000_00, -12_000_00, -6_500_00]
    assert txns[1].category == Category.UTILITIES.value


# ------------------------------------------------------------ correctness gates


def test_reupload_creates_zero_duplicates(session):
    first = ingest_file(session, FIXTURES / "hbl_jan2026.csv")
    again = ingest_file(session, FIXTURES / "hbl_jan2026.csv")
    assert first.txn_count == 4
    assert again.txn_count == 0
    assert again.skipped_duplicates == 4
    assert len(session.exec(select(Transaction)).all()) == 4


def test_failed_reconciliation_is_flagged_not_silent(session):
    """Statement claims closing 295,000 but txns sum to 290,000."""
    result = ingest_file(session, FIXTURES / "hbl_bad_reconcile.csv")
    assert result.status == "failed"
    assert result.reconciled is False
    assert result.discrepancy_minor == 5_000_00


def test_statement_balances_parsed_from_preamble():
    statement = parse_csv((FIXTURES / "hbl_jan2026.csv").read_bytes())
    assert statement.opening_balance_minor == 100_000_00
    assert statement.closing_balance_minor == 258_000_00
    assert statement.period_start.isoformat() == "2026-01-01"
    assert statement.period_end.isoformat() == "2026-01-10"
