"""The agent graph: router → planner → tool execution → explainer.

One router/planner that calls deterministic tools and one explainer — not six
co-equal "agents". State is a typed dict carried through a LangGraph
StateGraph. LangSmith tracing activates automatically via LANGCHAIN_* env
vars when configured.
"""
import uuid
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlmodel import Session

from .explainer_node import explain, explain_template
from .planner_node import plan
from .router_node import classify
from .tools import TOOLS, load_context

SMALLTALK_ANSWER = (
    "Hi! I can answer questions about your uploaded statements — try "
    "\"Can I afford a 250,000 PKR laptop next month?\", \"Where am I "
    "overspending?\", \"Create a 3-month savings plan for 300,000\", or "
    "\"What if I cancel Netflix?\""
)

CANNOT_PLAN_ANSWER = (
    "I understood the intent but couldn't extract concrete details "
    "(amount, date, or scenario). Try including a figure, e.g. "
    "\"Can I afford a 250,000 PKR laptop next month?\""
)


class AgentState(TypedDict, total=False):
    user_message: str
    intent: str
    tool_calls: list[dict]  # [{name, args}]
    tool_results: list[dict]
    final_answer: str
    trace_id: str
    explained_by: str  # llm | template | static


def build_graph(session: Session):
    def router_node(state: AgentState) -> AgentState:
        return {"intent": classify(state["user_message"])}

    def planner_node(state: AgentState) -> AgentState:
        if state["intent"] == "SMALLTALK":
            return {"tool_calls": []}
        as_of = load_context(session).as_of
        planned = plan(state["user_message"], state["intent"], as_of)
        if planned is None:
            return {"tool_calls": []}
        return {"tool_calls": [{"name": planned.tool, "args": planned.args}]}

    def executor_node(state: AgentState) -> AgentState:
        results = []
        for call in state.get("tool_calls", []):
            spec = TOOLS[call["name"]]
            args = spec.args_model.model_validate(call["args"])
            try:
                results.append(spec.fn(session, args))
            except Exception as e:  # surface tool failures as structured errors
                results.append({"result": {"error": str(e)}, "warnings": []})
        return {"tool_results": results}

    def explainer_node(state: AgentState) -> AgentState:
        if not state.get("tool_calls"):
            answer = (
                SMALLTALK_ANSWER
                if state["intent"] == "SMALLTALK"
                else CANNOT_PLAN_ANSWER
            )
            return {"final_answer": answer, "explained_by": "static"}
        call = state["tool_calls"][0]
        output = state["tool_results"][0]
        answer, via_llm = explain(
            state["user_message"], state["intent"], call["name"], output
        )
        return {"final_answer": answer, "explained_by": "llm" if via_llm else "template"}

    graph = StateGraph(AgentState)
    graph.add_node("router", router_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("explainer", explainer_node)
    graph.add_edge(START, "router")
    graph.add_edge("router", "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "explainer")
    graph.add_edge("explainer", END)
    return graph.compile()


def run_agent(session: Session, message: str) -> AgentState:
    compiled = build_graph(session)
    state: AgentState = {
        "user_message": message,
        "trace_id": str(uuid.uuid4()),
    }
    result = compiled.invoke(state)
    result.setdefault("tool_calls", [])
    result.setdefault("tool_results", [])
    return result
