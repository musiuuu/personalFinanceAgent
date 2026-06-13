"""POST /ingest — upload a statement (csv/pdf) or an invoice."""
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlmodel import Session

from ..db import get_session
from ..ingestion.pdf_ocr_parser import OCRUnavailableError
from ..ingestion.router import IngestResult, ingest_file
from ..models import Document

router = APIRouter(tags=["ingest"])


@router.post("/ingest", response_model=IngestResult)
async def ingest(
    file: UploadFile = File(...),
    kind: str = Form("statement"),  # statement | invoice
    session: Session = Depends(get_session),
):
    suffix = Path(file.filename or "upload").suffix.lower()
    if suffix not in (".csv", ".pdf"):
        raise HTTPException(400, "Only .csv and .pdf files are supported.")

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        if kind == "invoice":
            return _ingest_invoice(session, tmp_path, file.filename or "invoice.pdf")
        result = ingest_file(session, tmp_path)
        # ingest_file stored the temp name; keep the user's filename.
        doc = session.get(Document, result.doc_id)
        if doc is not None:
            doc.filename = file.filename or doc.filename
            session.add(doc)
            session.commit()
        return result
    except OCRUnavailableError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


def _ingest_invoice(session: Session, path: Path, filename: str) -> IngestResult:
    """Invoices are unstructured: extract text and index it for doc-QA."""
    from ..retrieval.vector import index_document

    if path.suffix == ".pdf":
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    else:
        text = path.read_text(errors="replace")

    if not text.strip():
        raise HTTPException(422, "No extractable text found in the invoice.")

    doc = Document(filename=filename, file_type="invoice", status="parsed")
    session.add(doc)
    session.flush()
    chunks = index_document(session, doc.id, text)
    session.commit()
    return IngestResult(
        doc_id=doc.id,
        status="parsed",
        reconciled=None,
        discrepancy_minor=None,
        txn_count=0,
        skipped_duplicates=0,
        file_type="invoice",
        bank_hint=f"{chunks} chunks indexed",
    )
