"""GET /dashboard/* — chart data for the frontend. All money in minor units;
the UI converts at the edge."""
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from ..agent.tools import load_context
from ..config import get_settings
from ..db import get_session
from ..engine.anomalies import detect_anomalies
from ..engine.cashflow import monthly_cashflow
from ..engine.recurring import detect_recurring
from ..models import Document, Transaction
from ..schemas import YearMonth

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def summary(session: Session = Depends(get_session)):
    ctx = load_context(session)
    docs = session.exec(select(Document).order_by(Document.ingested_at.desc())).all()
    return {
        "current_balance_minor": ctx.current_balance_minor,
        "as_of": ctx.as_of.isoformat(),
        "txn_count": len(ctx.txns),
        "warnings": ctx.warnings,
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "status": d.status,
                "discrepancy_minor": d.reconcile_discrepancy_minor,
                "period_start": d.statement_period_start.isoformat()
                if d.statement_period_start else None,
                "period_end": d.statement_period_end.isoformat()
                if d.statement_period_end else None,
            }
            for d in docs
        ],
    }


@router.get("/cashflow")
def cashflow(months: int = Query(6, ge=1, le=24), session: Session = Depends(get_session)):
    ctx = load_context(session)
    month = YearMonth.of(ctx.as_of)
    series = []
    for _ in range(months):
        series.append(monthly_cashflow(ctx.txns, month).model_dump(mode="json"))
        month = month.prev()
    series.reverse()
    return {"months": series}


@router.get("/categories")
def categories(month: str | None = None, session: Session = Depends(get_session)):
    ctx = load_context(session)
    ym = YearMonth.parse(month) if month else YearMonth.of(ctx.as_of)
    return monthly_cashflow(ctx.txns, ym).model_dump(mode="json")


@router.get("/transactions")
def transactions(
    month: str | None = None,
    category: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    query = select(Transaction).order_by(Transaction.txn_date.desc(), Transaction.id.desc())
    rows = session.exec(query).all()
    out = []
    for r in rows:
        if month and r.txn_date.strftime("%Y-%m") != month:
            continue
        if category and r.category != category:
            continue
        out.append(
            {
                "id": r.id,
                "txn_date": r.txn_date.isoformat(),
                "amount_minor": r.amount_minor,
                "merchant": r.merchant_normalized,
                "raw_description": r.raw_description,
                "category": r.category,
            }
        )
        if len(out) >= limit:
            break
    return {"transactions": out}


@router.get("/anomalies")
def anomalies(session: Session = Depends(get_session)):
    ctx = load_context(session)
    found = detect_anomalies(ctx.txns, mad_k=get_settings().anomaly_mad_k)
    return {"anomalies": [a.model_dump(mode="json") for a in found]}


@router.get("/recurring")
def recurring(session: Session = Depends(get_session)):
    ctx = load_context(session)
    groups = detect_recurring(ctx.txns)
    return {"recurring": [g.model_dump(mode="json") for g in groups]}
