"""Lightweight agent eval (spec Section 12.5).

Scripted prompts across the intents assert (a) the right tool was selected
and (b) every number in the final answer traces back to the tool result —
the Section 8.4 guardrail, checked end to end. Runs entirely offline on the
deterministic heuristic router/planner/template-explainer path.
"""
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.agent.graph import run_agent
from app.agent.guardrail import find_violations
from app.models import Account, Document, Transaction

# (prompt, expected_intent, expected_tool or None)
EVAL_CASES = [
    ("Can I afford a 250,000 PKR laptop next month?", "AFFORDABILITY", "affordability_tool"),
    ("Is a PKR 90,000 phone within reach next month?", "AFFORDABILITY", "affordability_tool"),
    ("Can I afford a 2 lakh sofa in 2 months?", "AFFORDABILITY", "affordability_tool"),
    ("Where am I overspending?", "DIAGNOSIS", "cashflow_tool"),
    ("Why did my cash flow drop this month?", "DIAGNOSIS", "cashflow_tool"),
    ("Compare my last two months of spending", "DIAGNOSIS", "cashflow_tool"),
    ("Any unusual transactions recently?", "DIAGNOSIS", "anomaly_tool"),
    ("Create a 3-month savings plan for 300,000 PKR", "PLANNING", "savings_plan_tool"),
    ("I want to save 500,000 in six months", "PLANNING", "savings_plan_tool"),
    ("What if I cancel my Netflix subscription?", "SIMULATION", "simulate_tool"),
    ("What if I cut dining by 30%?", "SIMULATION", "simulate_tool"),
    ("What if I cancel Spotify and cut groceries by 20%?", "SIMULATION", "simulate_tool"),
    ("How much did I spend on groceries in March?", "SQL_QUERY", "sql_tool"),
    ("List transactions over 10,000 rupees", "SQL_QUERY", "sql_tool"),
    ("What were the payment terms on the laptop invoice?", "DOC_QA", "doc_qa_tool"),
    ("hello", "SMALLTALK", None),
]


@pytest.fixture
def session(history):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        account = Account(name="Primary")
        s.add(account)
        s.flush()
        doc = Document(filename="seed.csv", file_type="csv",
                       account_id=account.id, status="reconciled")
        s.add(doc)
        s.flush()
        for t in history:
            s.add(
                Transaction(
                    account_id=account.id,
                    source_doc_id=doc.id,
                    txn_date=t.txn_date,
                    amount_minor=t.amount_minor,
                    raw_description=t.raw_description,
                    merchant_normalized=t.merchant,
                    category=t.category.value,
                    dedup_hash=f"seed-{t.txn_id}",
                )
            )
        s.commit()
        yield s


@pytest.mark.parametrize("prompt,intent,tool", EVAL_CASES)
def test_right_tool_selected(session, prompt, intent, tool):
    state = run_agent(session, prompt)
    assert state["intent"] == intent
    called = [c["name"] for c in state["tool_calls"]]
    if tool is None:
        assert called == []
    else:
        assert called == [tool]
    assert state["final_answer"]


@pytest.mark.parametrize(
    "prompt",
    [
        "Can I afford a 250,000 PKR laptop next month?",
        "Create a 3-month savings plan for 300,000 PKR",
        "Why did my cash flow drop this month?",
        "What if I cut dining by 30%?",
        "Any unusual transactions recently?",
    ],
)
def test_final_answer_numbers_trace_to_tool_results(session, prompt):
    """The explainer guardrail, asserted end to end: every figure in the
    answer must exist in the structured tool output."""
    state = run_agent(session, prompt)
    assert state["tool_results"]
    violations = find_violations(state["final_answer"], state["tool_results"])
    assert violations == [], f"invented numbers: {violations}"


def test_unreconciled_data_is_never_silent(session):
    """Add a failed statement: its txns are excluded AND the answer warns."""
    bad_doc = Document(filename="bad.csv", file_type="csv", status="failed",
                       reconcile_discrepancy_minor=5_000_00)
    session.add(bad_doc)
    session.flush()
    session.add(
        Transaction(
            account_id=1, source_doc_id=bad_doc.id,
            txn_date=__import__("datetime").date(2026, 3, 25),
            amount_minor=-99_999_00, raw_description="GHOST CHARGE",
            merchant_normalized="GHOST", category="OTHER", dedup_hash="bad-1",
        )
    )
    session.commit()

    state = run_agent(session, "Why did my cash flow drop this month?")
    answer = state["final_answer"]
    assert "failed reconciliation" in answer
    # The ghost transaction must not contaminate the numbers.
    assert "99,999" not in answer
