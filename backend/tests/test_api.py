"""End-to-end API tests: upload → reconcile → dashboard → chat."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLES = Path(__file__).parent.parent.parent / "sample_data"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _upload(client, path: Path):
    with path.open("rb") as f:
        return client.post(
            "/api/ingest", files={"file": (path.name, f, "text/csv")}
        )


def test_full_flow(client):
    # 1. Upload both sample statements; both must reconcile.
    for name in ["hbl_statement_2026_q1.csv", "hbl_statement_2026_q2.csv"]:
        r = _upload(client, SAMPLES / name)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "reconciled"
        assert body["reconciled"] is True

    # 2. Re-upload: zero duplicates (acceptance criterion).
    r = _upload(client, SAMPLES / "hbl_statement_2026_q1.csv")
    assert r.json()["txn_count"] == 0
    assert r.json()["skipped_duplicates"] > 0

    # 3. Dashboard endpoints.
    summary = client.get("/api/dashboard/summary").json()
    assert summary["txn_count"] == 67
    assert summary["current_balance_minor"] == 791_600_00  # printed closing balance

    cashflow = client.get("/api/dashboard/cashflow?months=6").json()["months"]
    assert len(cashflow) == 6
    assert all(m["net_minor"] == m["income_minor"] - m["expense_minor"] for m in cashflow)

    recurring = client.get("/api/dashboard/recurring").json()["recurring"]
    merchants = {g["merchant"] for g in recurring}
    assert "NETFLIX" in merchants
    netflix = next(g for g in recurring if g["merchant"] == "NETFLIX")
    assert netflix["price_change"] is True  # 2,000 → 2,600 in May

    anomalies = client.get("/api/dashboard/anomalies").json()["anomalies"]
    kinds = {a["kind"] for a in anomalies}
    assert "new_large_merchant" in kinds  # GOLD SOUK 90k
    assert "duplicate_charge" in kinds  # double FOODPANDA in April

    # 4. Chat: affordability with full breakdown, numbers guarded.
    r = client.post(
        "/api/chat", json={"message": "Can I afford a 250,000 PKR laptop next month?"}
    )
    body = r.json()
    assert body["intent"] == "AFFORDABILITY"
    assert body["tool_calls"][0]["name"] == "affordability_tool"
    assert body["data"]["result"]["purchase_minor"] == 250_000_00
    assert "PKR" in body["answer"]

    # 5. Chat: simulation.
    r = client.post("/api/chat", json={"message": "What if I cancel Netflix?"})
    body = r.json()
    assert body["intent"] == "SIMULATION"
    assert body["data"]["result"]["monthly_impact_minor"] > 0


def test_failed_statement_visible_in_summary(client):
    r = _upload(client, FIXTURES / "hbl_bad_reconcile.csv")
    assert r.json()["status"] == "failed"
    summary = client.get("/api/dashboard/summary").json()
    assert summary["documents"][0]["status"] == "failed"
    assert summary["warnings"]


def test_goals_crud_and_projection(client):
    _upload(client, SAMPLES / "hbl_statement_2026_q1.csv")
    r = client.post(
        "/api/goals",
        json={
            "name": "Laptop",
            "target_amount_minor": 30_000_000,
            "target_date": "2026-09-01",
        },
    )
    assert r.status_code == 200
    goal_id = r.json()["id"]

    listed = client.get("/api/goals").json()["goals"]
    assert listed[0]["name"] == "Laptop"
    assert listed[0]["months_to_complete"] is not None

    r = client.patch(f"/api/goals/{goal_id}", json={"saved_so_far_minor": 15_000_000})
    assert r.json()["saved_so_far_minor"] == 15_000_000


def test_unsupported_file_rejected(client):
    r = client.post("/api/ingest", files={"file": ("x.docx", b"nope", "application/x")})
    assert r.status_code == 400
