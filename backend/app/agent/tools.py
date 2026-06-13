"""Tool wrappers around the deterministic engine and retrieval.

These are the ONLY things the planner may call. Every tool takes a validated
Pydantic args model, reads transactions from the DB, calls pure engine
functions, and returns a structured Pydantic result. No tool lets the LLM
near raw arithmetic.
"""
from datetime import date
from typing import Callable

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import get_settings
from ..db import sqlite_path
from ..engine.affordability import can_afford
from ..engine.anomalies import detect_anomalies
from ..engine.cashflow import cashflow_delta, monthly_cashflow
from ..engine.forecast import forecast_period
from ..engine.recurring import detect_recurring
from ..engine.savings_plan import savings_plan
from ..engine.simulate import simulate
from ..models import Category, Document, Transaction
from ..schemas import ScenarioDelta, Txn, YearMonth

# ----------------------------------------------------------------- context


class LedgerContext(BaseModel):
    txns: list[Txn]
    current_balance_minor: int
    as_of: date
    warnings: list[str] = []


def load_context(session: Session) -> LedgerContext:
    """Load the ledger. Transactions from unreconciled (failed) statements are
    EXCLUDED and a warning is attached — the agent must never silently answer
    on data that failed the balance-integrity check."""
    failed_docs = session.exec(
        select(Document).where(Document.status == "failed")
    ).all()
    failed_ids = {d.id for d in failed_docs}

    rows = session.exec(
        select(Transaction).order_by(Transaction.txn_date, Transaction.id)
    ).all()
    txns = [
        Txn(
            txn_date=r.txn_date,
            amount_minor=r.amount_minor,
            category=Category(r.category) if r.category else Category.OTHER,
            merchant=r.merchant_normalized,
            raw_description=r.raw_description,
            txn_id=r.id,
        )
        for r in rows
        if r.source_doc_id not in failed_ids
    ]

    balance = 0
    included = [r for r in rows if r.source_doc_id not in failed_ids]
    if included:
        last = included[-1]
        if last.balance_after_minor is not None:
            balance = last.balance_after_minor
        else:
            balance = sum(r.amount_minor for r in included)

    warnings = [
        f"Statement '{d.filename}' failed reconciliation "
        f"(discrepancy {(d.reconcile_discrepancy_minor or 0) / 100:,.2f} PKR); "
        f"its transactions are excluded from this answer."
        for d in failed_docs
    ]
    as_of = txns[-1].txn_date if txns else date.today()
    return LedgerContext(
        txns=txns, current_balance_minor=balance, as_of=as_of, warnings=warnings
    )


# ------------------------------------------------------------------- args


class AffordabilityArgs(BaseModel):
    purchase_minor: int = Field(gt=0, description="purchase amount in paisa")
    target_date: date


class SavingsPlanArgs(BaseModel):
    goal_minor: int = Field(gt=0)
    horizon_months: int = Field(ge=1, le=120)


class CashflowArgs(BaseModel):
    month: str | None = None  # YYYY-MM; defaults to latest month with data
    compare_month: str | None = None  # when set → month-over-month diagnosis


class SimulateArgs(BaseModel):
    deltas: list[ScenarioDelta] = Field(min_length=1)
    horizon_months: int = Field(default=3, ge=1, le=60)


class AnomalyArgs(BaseModel):
    window_months: int = Field(default=3, ge=1, le=24)


class RecurringArgs(BaseModel):
    pass


class NLQueryArgs(BaseModel):
    nl_query: str = Field(min_length=1)


# ------------------------------------------------------------------- tools


def affordability_tool(session: Session, args: AffordabilityArgs) -> dict:
    ctx = load_context(session)
    settings = get_settings()
    forecast = forecast_period(
        ctx.txns, n_lookback=settings.forecast_lookback_months, as_of=ctx.as_of
    )
    result = can_afford(
        args.purchase_minor,
        args.target_date,
        ctx.current_balance_minor,
        forecast,
        settings.safety_buffer_minor,
        as_of=ctx.as_of,
    )
    return {"result": result.model_dump(mode="json"), "warnings": ctx.warnings}


def savings_plan_tool(session: Session, args: SavingsPlanArgs) -> dict:
    ctx = load_context(session)
    settings = get_settings()
    forecast = forecast_period(
        ctx.txns, n_lookback=settings.forecast_lookback_months, as_of=ctx.as_of
    )
    result = savings_plan(
        args.goal_minor, args.horizon_months, ctx.current_balance_minor, forecast
    )
    return {"result": result.model_dump(mode="json"), "warnings": ctx.warnings}


def cashflow_tool(session: Session, args: CashflowArgs) -> dict:
    ctx = load_context(session)
    latest = YearMonth.of(ctx.as_of)
    month = YearMonth.parse(args.month) if args.month else latest
    if args.compare_month:
        other = YearMonth.parse(args.compare_month)
        # Order chronologically: a = earlier, b = later.
        a, b = (other, month) if other <= month else (month, other)
        result = cashflow_delta(ctx.txns, a, b)
    else:
        result = monthly_cashflow(ctx.txns, month)
    return {"result": result.model_dump(mode="json"), "warnings": ctx.warnings}


def simulate_tool(session: Session, args: SimulateArgs) -> dict:
    ctx = load_context(session)
    settings = get_settings()
    result = simulate(
        ctx.txns,
        args.deltas,
        args.horizon_months,
        current_balance_minor=ctx.current_balance_minor,
        as_of=ctx.as_of,
        n_lookback=settings.forecast_lookback_months,
    )
    return {"result": result.model_dump(mode="json"), "warnings": ctx.warnings}


def anomaly_tool(session: Session, args: AnomalyArgs) -> dict:
    ctx = load_context(session)
    cutoff_month = YearMonth.of(ctx.as_of)
    for _ in range(args.window_months - 1):
        cutoff_month = cutoff_month.prev()
    cutoff = date(cutoff_month.year, cutoff_month.month, 1)
    window = [t for t in ctx.txns if t.txn_date >= cutoff]
    found = detect_anomalies(window, mad_k=get_settings().anomaly_mad_k)
    return {
        "result": {"anomalies": [a.model_dump(mode="json") for a in found]},
        "warnings": ctx.warnings,
    }


def recurring_tool(session: Session, args: RecurringArgs) -> dict:
    ctx = load_context(session)
    groups = detect_recurring(ctx.txns)
    return {
        "result": {"recurring": [g.model_dump(mode="json") for g in groups]},
        "warnings": ctx.warnings,
    }


def sql_tool(session: Session, args: NLQueryArgs) -> dict:
    from ..retrieval.text_to_sql import answer_with_sql

    result = answer_with_sql(args.nl_query, sqlite_path())
    return {"result": result.model_dump(mode="json"), "warnings": []}


def doc_qa_tool(session: Session, args: NLQueryArgs) -> dict:
    from ..retrieval.vector import search

    hits = search(session, args.nl_query)
    return {
        "result": {
            "chunks": [
                {"score": round(score, 4), "text": chunk.text, "doc_id": chunk.source_doc_id}
                for score, chunk in hits
            ]
        },
        "warnings": [],
    }


class ToolSpec(BaseModel):
    name: str
    description: str
    args_model: type[BaseModel]
    fn: Callable[..., dict]

    model_config = {"arbitrary_types_allowed": True}


TOOLS: dict[str, ToolSpec] = {
    spec.name: spec
    for spec in [
        ToolSpec(
            name="affordability_tool",
            description="Can the user afford a purchase of purchase_minor paisa by target_date?",
            args_model=AffordabilityArgs,
            fn=affordability_tool,
        ),
        ToolSpec(
            name="savings_plan_tool",
            description="Build a monthly savings schedule for goal_minor paisa over horizon_months.",
            args_model=SavingsPlanArgs,
            fn=savings_plan_tool,
        ),
        ToolSpec(
            name="cashflow_tool",
            description="Monthly cashflow summary (month=YYYY-MM), or month-over-month diagnosis when compare_month is set.",
            args_model=CashflowArgs,
            fn=cashflow_tool,
        ),
        ToolSpec(
            name="simulate_tool",
            description="What-if scenario: list of deltas (cut_category pct / cancel merchant / add_expense / income_change) over horizon_months.",
            args_model=SimulateArgs,
            fn=simulate_tool,
        ),
        ToolSpec(
            name="anomaly_tool",
            description="Unusual transactions in the last window_months.",
            args_model=AnomalyArgs,
            fn=anomaly_tool,
        ),
        ToolSpec(
            name="recurring_tool",
            description="Detected subscriptions/recurring payments incl. price changes.",
            args_model=RecurringArgs,
            fn=recurring_tool,
        ),
        ToolSpec(
            name="sql_tool",
            description="Answer a structured data question by querying the transaction store (read-only SQL).",
            args_model=NLQueryArgs,
            fn=sql_tool,
        ),
        ToolSpec(
            name="doc_qa_tool",
            description="Answer a question about uploaded unstructured documents (invoices, terms).",
            args_model=NLQueryArgs,
            fn=doc_qa_tool,
        ),
    ]
}
