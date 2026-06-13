"""The text-PDF ingestion path, exercised on the committed sample statement.

Confirms a text-layer PDF is detected as `pdf_text` (not routed to OCR) and
that it parses and reconciles end to end.
"""
from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.ingestion.router import detect_file_type, ingest_file
from app.models import Transaction

SAMPLE_PDF = Path(__file__).parent.parent.parent / "sample_data" / "hbl_statement_2026_q1.pdf"


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="sample PDF not generated")
def test_text_pdf_detected_and_reconciles(session):
    assert detect_file_type(SAMPLE_PDF) == "pdf_text"

    result = ingest_file(session, SAMPLE_PDF)
    assert result.file_type == "pdf_text"
    assert result.reconciled is True
    assert result.status == "reconciled"
    assert result.txn_count == 33

    txns = session.exec(select(Transaction).order_by(Transaction.txn_date)).all()
    # Signs recovered correctly from the running-balance column.
    assert txns[0].amount_minor == 260_000_00  # salary inflow
    assert txns[1].amount_minor == -65_000_00  # rent outflow
