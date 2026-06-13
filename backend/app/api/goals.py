"""Goals & budgets CRUD, with engine-computed goal projections."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..agent.tools import load_context
from ..config import get_settings
from ..db import get_session
from ..engine.forecast import forecast_period
from ..models import Budget, Goal

router = APIRouter(tags=["goals"])


class GoalIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    target_amount_minor: int = Field(gt=0)
    target_date: date
    saved_so_far_minor: int = Field(default=0, ge=0)


class GoalPatch(BaseModel):
    name: str | None = None
    target_amount_minor: int | None = Field(default=None, gt=0)
    target_date: date | None = None
    saved_so_far_minor: int | None = Field(default=None, ge=0)


def _project(goal: Goal, surplus_minor: int, as_of: date) -> dict:
    remaining = max(0, goal.target_amount_minor - goal.saved_so_far_minor)
    months_to_complete = None
    projected_completion = None
    if remaining == 0:
        months_to_complete = 0
        projected_completion = as_of.isoformat()
    elif surplus_minor > 0:
        months_to_complete = -(-remaining // surplus_minor)  # ceil
        year = as_of.year + (as_of.month - 1 + months_to_complete) // 12
        month = (as_of.month - 1 + months_to_complete) % 12 + 1
        projected_completion = date(year, month, 1).isoformat()
    return {
        **goal.model_dump(mode="json"),
        "remaining_minor": remaining,
        "monthly_surplus_minor": surplus_minor,
        "months_to_complete": months_to_complete,
        "projected_completion": projected_completion,
        "on_track": (
            projected_completion is not None
            and projected_completion <= goal.target_date.isoformat()
        ),
    }


@router.get("/goals")
def list_goals(session: Session = Depends(get_session)):
    ctx = load_context(session)
    forecast = forecast_period(
        ctx.txns, n_lookback=get_settings().forecast_lookback_months, as_of=ctx.as_of
    )
    goals = session.exec(select(Goal)).all()
    return {
        "goals": [_project(g, forecast.expected_surplus_minor, ctx.as_of) for g in goals]
    }


@router.post("/goals")
def create_goal(payload: GoalIn, session: Session = Depends(get_session)):
    goal = Goal(**payload.model_dump())
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


@router.patch("/goals/{goal_id}")
def patch_goal(goal_id: int, payload: GoalPatch, session: Session = Depends(get_session)):
    goal = session.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(404, "Goal not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(goal, key, value)
    session.add(goal)
    session.commit()
    session.refresh(goal)
    return goal


class BudgetIn(BaseModel):
    category: str
    monthly_limit_minor: int = Field(gt=0)


@router.get("/budgets")
def list_budgets(session: Session = Depends(get_session)):
    return {"budgets": session.exec(select(Budget)).all()}


@router.post("/budgets")
def create_budget(payload: BudgetIn, session: Session = Depends(get_session)):
    existing = session.exec(
        select(Budget).where(Budget.category == payload.category)
    ).first()
    if existing:
        existing.monthly_limit_minor = payload.monthly_limit_minor
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing
    budget = Budget(**payload.model_dump())
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget
