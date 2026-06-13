"""Ingestion orchestration.

file → type detection → parser → normalize → categorize → reconcile → DB

The reconciliation gate is enforced here: a statement whose transactions do
not sum from the printed opening balance to the printed closing balance is
stored with status="failed" and its discrepancy, and downstream consumers
(the agent, the dashboard) must surface that instead of silently answering.
"""
from pathlib import Path

from pydantic import BaseModel
from sqlmodel import Session, select

from ..config import get_settings
from ..engine.reconcile import reconcile
from ..categorize.service import categorize
from ..models import Account, Document, Transaction
from ..schemas import Txn
from .csv_parser import parse_csv
from .normalize import clean_merchant, dedup_hash
from .types import ParsedStatement


class IngestResult(BaseModel):
    doc_id: int
    status: str  # reconciled | parsed | failed
    reconciled: bool | None  # None = statement had no printed balances
    discrepancy_minor: int | None
    txn_count: int
    skipped_duplicates: int
    file_type: str
    bank_hint: str | None = None


def detect_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".pdf":
        import pdfplumber

        threshold = get_settings().pdf_text_min_chars_per_page
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                if len(page.extract_text() or "") > threshold:
                    return "pdf_text"
        return "pdf_ocr"
    raise ValueError(f"Unsupported file type: {suffix} (use .csv or .pdf)")


def parse_file(path: Path, file_type: str) -> ParsedStatement:
    if file_type == "csv":
        return parse_csv(path.read_bytes())
    if file_type == "pdf_text":
        from .pdf_text_parser import parse_pdf_text

        return parse_pdf_text(str(path))
    if file_type == "pdf_ocr":
        from .pdf_ocr_parser import parse_pdf_ocr

        return parse_pdf_ocr(str(path))
    raise ValueError(f"Unknown file type: {file_type}")


def _default_account(session: Session) -> Account:
    account = session.exec(select(Account)).first()
    if account is None:
        account = Account(name="Primary", currency="PKR", opening_balance_minor=0)
        session.add(account)
        session.flush()
    return account


def ingest_file(
    session: Session, path: Path, account_id: int | None = None
) -> IngestResult:
    file_type = detect_file_type(path)
    statement = parse_file(path, file_type)

    if account_id is None:
        account_id = _default_account(session).id

    document = Document(
        filename=path.name,
        file_type=file_type,
        account_id=account_id,
        statement_period_start=statement.period_start,
        statement_period_end=statement.period_end,
        opening_balance_minor=statement.opening_balance_minor,
        closing_balance_minor=statement.closing_balance_minor,
        status="parsed",
    )
    session.add(document)
    session.flush()

    existing_hashes = set(
        session.exec(
            select(Transaction.dedup_hash).where(Transaction.account_id == account_id)
        ).all()
    )

    inserted: list[Transaction] = []
    skipped = 0
    statement_txns: list[Txn] = []  # ALL parsed rows — reconciliation must see
    # the full statement even when some rows were already in the DB.
    for row in statement.rows:
        merchant = clean_merchant(row.description)
        category = categorize(session, merchant, row.description)
        statement_txns.append(
            Txn(
                txn_date=row.txn_date,
                amount_minor=row.amount_minor,
                category=category,
                merchant=merchant,
                raw_description=row.description,
            )
        )
        h = dedup_hash(account_id, row.txn_date, row.amount_minor, row.description)
        if h in existing_hashes:
            skipped += 1
            continue
        existing_hashes.add(h)
        txn = Transaction(
            account_id=account_id,
            source_doc_id=document.id,
            txn_date=row.txn_date,
            amount_minor=row.amount_minor,
            raw_description=row.description,
            merchant_normalized=merchant,
            category=category.value,
            balance_after_minor=row.balance_after_minor,
            dedup_hash=h,
        )
        session.add(txn)
        inserted.append(txn)

    reconciled: bool | None = None
    discrepancy: int | None = None
    if (
        statement.opening_balance_minor is not None
        and statement.closing_balance_minor is not None
    ):
        result = reconcile(
            statement.opening_balance_minor,
            statement_txns,
            statement.closing_balance_minor,
        )
        reconciled = result.ok
        discrepancy = result.discrepancy_minor
        document.status = "reconciled" if result.ok else "failed"
        document.reconcile_discrepancy_minor = result.discrepancy_minor

    session.commit()
    return IngestResult(
        doc_id=document.id,
        status=document.status,
        reconciled=reconciled,
        discrepancy_minor=discrepancy,
        txn_count=len(inserted),
        skipped_duplicates=skipped,
        file_type=file_type,
        bank_hint=statement.bank_hint,
    )
