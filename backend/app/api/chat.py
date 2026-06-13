"""POST /chat — the agent endpoint. Returns prose AND the structured tool
payload so the frontend can render charts/tables under the answer."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..agent.graph import run_agent
from ..db import get_session

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    answer: str
    intent: str
    tool_calls: list[dict]
    data: dict | None = None  # structured result of the first tool call
    trace_id: str
    explained_by: str


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, session: Session = Depends(get_session)):
    state = run_agent(session, request.message)
    results = state.get("tool_results", [])
    return ChatResponse(
        answer=state["final_answer"],
        intent=state["intent"],
        tool_calls=state["tool_calls"],
        data=results[0] if results else None,
        trace_id=state["trace_id"],
        explained_by=state.get("explained_by", "template"),
    )
