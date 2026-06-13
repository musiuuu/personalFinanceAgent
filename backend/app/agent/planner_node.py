"""The planner decides which tool to call and with which arguments.

Hard rule (Section 8.3 of the spec): the LLM outputs ONLY a tool name and a
JSON argument object. The arguments are parsed into the tool's Pydantic model
and rejected if invalid (one re-prompt, then error/fallback). The LLM never
sees raw balances to add up.
"""
import json
import re
from datetime import date

from pydantic import BaseModel, ValidationError

from ..models import Category
from ..schemas import ScenarioDelta
from .llm import complete
from .parsing import (
    parse_amounts_pkr_minor,
    parse_horizon_months,
    parse_percentage,
    parse_target_date,
)
from .tools import TOOLS


class PlannedCall(BaseModel):
    tool: str
    args: dict


_PROMPT = """You are the planner of a personal-finance agent. Pick ONE tool and extract its arguments from the user's message. You never compute financial figures — a deterministic engine does that.

Today's date: {as_of}
Intent: {intent}

Tools and their JSON argument schemas:
{tool_docs}

Notes:
- All money arguments are in MINOR units (paisa): multiply PKR by 100.
- Dates are ISO yyyy-mm-dd. Months are 'YYYY-MM' strings.
- simulate_tool deltas: {{"type":"cut_category","category":"DINING","pct":30}} |
  {{"type":"cancel","merchant":"NETFLIX"}} |
  {{"type":"add_expense","amount_minor":1000000,"recurring":true}} |
  {{"type":"income_change","amount_minor":-2000000}}
- Categories must be from: {categories}

User message: {message}

Respond with ONLY a JSON object: {{"tool": "<name>", "args": {{...}}}}"""

_INTENT_DEFAULT_TOOL = {
    "AFFORDABILITY": "affordability_tool",
    "PLANNING": "savings_plan_tool",
    "DIAGNOSIS": "cashflow_tool",
    "SIMULATION": "simulate_tool",
    "SQL_QUERY": "sql_tool",
    "DOC_QA": "doc_qa_tool",
}


def _tool_docs() -> str:
    lines = []
    for spec in TOOLS.values():
        schema = spec.args_model.model_json_schema()
        props = {
            k: v.get("type", v.get("anyOf", "any"))
            for k, v in schema.get("properties", {}).items()
        }
        lines.append(f"- {spec.name}: {spec.description}  args={json.dumps(props)}")
    return "\n".join(lines)


def _validate(call: dict) -> PlannedCall | None:
    tool = call.get("tool")
    if tool not in TOOLS:
        return None
    try:
        args_model = TOOLS[tool].args_model.model_validate(call.get("args") or {})
    except ValidationError:
        return None
    return PlannedCall(tool=tool, args=args_model.model_dump(mode="json"))


def _extract_json(text: str) -> dict | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def plan_with_llm(message: str, intent: str, as_of: date) -> PlannedCall | None:
    prompt = _PROMPT.format(
        as_of=as_of.isoformat(),
        intent=intent,
        tool_docs=_tool_docs(),
        categories=", ".join(c.value for c in Category),
        message=message,
    )
    for attempt in range(2):  # one re-prompt on invalid args
        raw = complete(prompt, smart=True)
        if raw is None:
            return None
        parsed = _extract_json(raw)
        if parsed is not None:
            validated = _validate(parsed)
            if validated is not None:
                return validated
        prompt += (
            "\n\nYour previous response was not a valid tool call "
            "(unknown tool or arguments failed schema validation). "
            "Respond with ONLY the JSON object."
        )
    return None


# ------------------------------------------------------- heuristic fallback


def _plan_simulation(message: str) -> list[ScenarioDelta]:
    deltas: list[ScenarioDelta] = []
    lowered = message.lower()
    if m := re.search(r"cancel(?:ling)?\s+(?:my\s+)?([a-z0-9+& ]{2,30}?)(?:\s+subscription)?(?:[,.?]|$|\s+and\b)", lowered):
        deltas.append(ScenarioDelta(type="cancel", merchant=m.group(1).strip()))
    pct = parse_percentage(message)
    for cat in Category:
        if cat.value.lower() in lowered or cat.name.replace("_", " ").lower() in lowered:
            if pct is not None and re.search(r"cut|reduce|lower|trim", lowered):
                deltas.append(ScenarioDelta(type="cut_category", category=cat, pct=pct))
    if not deltas and pct is not None:
        # "cut dining out by 30%" with fuzzy category words
        synonyms = {
            "dining": Category.DINING, "eating out": Category.DINING,
            "food delivery": Category.DINING, "groceries": Category.GROCERIES,
            "shopping": Category.SHOPPING, "fuel": Category.FUEL,
            "transport": Category.TRANSPORT, "rides": Category.TRANSPORT,
        }
        for word, cat in synonyms.items():
            if word in lowered:
                deltas.append(ScenarioDelta(type="cut_category", category=cat, pct=pct))
                break
    return deltas


def plan_heuristic(message: str, intent: str, as_of: date) -> PlannedCall | None:
    amounts = parse_amounts_pkr_minor(message)
    if intent == "AFFORDABILITY":
        if not amounts:
            return None
        return _validate(
            {
                "tool": "affordability_tool",
                "args": {
                    "purchase_minor": max(amounts),
                    "target_date": parse_target_date(message, as_of).isoformat(),
                },
            }
        )
    if intent == "PLANNING":
        if not amounts:
            return None
        horizon = parse_horizon_months(message, default=3)
        return _validate(
            {
                "tool": "savings_plan_tool",
                "args": {"goal_minor": max(amounts), "horizon_months": horizon},
            }
        )
    if intent == "DIAGNOSIS":
        latest = f"{as_of.year:04d}-{as_of.month:02d}"
        prev_y, prev_m = (as_of.year, as_of.month - 1) if as_of.month > 1 else (as_of.year - 1, 12)
        if re.search(r"anomal|unusual|weird|suspicious", message, re.I):
            return _validate({"tool": "anomaly_tool", "args": {}})
        return _validate(
            {
                "tool": "cashflow_tool",
                "args": {"month": latest, "compare_month": f"{prev_y:04d}-{prev_m:02d}"},
            }
        )
    if intent == "SIMULATION":
        deltas = _plan_simulation(message)
        if not deltas:
            return None
        horizon = parse_horizon_months(message, default=3)
        return _validate(
            {
                "tool": "simulate_tool",
                "args": {
                    "deltas": [d.model_dump(mode="json") for d in deltas],
                    "horizon_months": horizon,
                },
            }
        )
    if intent == "SQL_QUERY":
        return _validate({"tool": "sql_tool", "args": {"nl_query": message}})
    if intent == "DOC_QA":
        return _validate({"tool": "doc_qa_tool", "args": {"nl_query": message}})
    return None


def plan(message: str, intent: str, as_of: date) -> PlannedCall | None:
    if intent == "SMALLTALK":
        return None
    planned = plan_with_llm(message, intent, as_of)
    if planned is not None:
        return planned
    return plan_heuristic(message, intent, as_of)
