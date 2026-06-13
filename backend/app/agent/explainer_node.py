"""Turn structured tool results into prose — and nothing more.

The LLM is instructed to use only the numbers in the result. The guardrail
then verifies that mechanically; on violation we regenerate once with
feedback, and if it still invents figures we fall back to a deterministic
template. The template path is also the offline mode.
"""
import json

from .guardrail import find_violations
from .llm import complete

_PROMPT = """You are the explainer of a personal-finance agent. A deterministic engine already computed the answer; your ONLY job is to phrase it clearly.

User question: {message}
Intent: {intent}
Tool called: {tool}
Tool result (JSON, money fields ending in _minor are in paisa — divide by 100 for PKR):
{result}

Rules — non-negotiable:
- Use ONLY numbers present in the JSON (you may divide *_minor values by 100 to show PKR).
- NEVER compute new figures (no additions, differences, or percentages of your own).
- Format money as PKR with thousand separators, e.g. PKR 238,000.
- 2–5 sentences, direct, friendly, lead with the verdict. If 'warnings' is non-empty, mention them.

Answer:"""


def _fmt(minor: int | None) -> str:
    if minor is None:
        return "PKR ?"
    return f"PKR {minor / 100:,.0f}"


# ----------------------------------------------------- deterministic templates


def _explain_affordability(r: dict) -> str:
    verdict = "Yes — you can afford it." if r["affordable"] else "Not safely, no."
    lines = [
        verdict,
        f"Buying for {_fmt(r['purchase_minor'])} by {r['target_date']} "
        f"({r['months_until_target']} month(s) away):",
        f"- Current balance: {_fmt(r['current_balance_minor'])}",
        f"- Expected income until then: {_fmt(r['expected_income_total_minor'])}",
        f"- Expected bills/recurring: {_fmt(r['expected_recurring_total_minor'])}",
        f"- Expected variable spending: {_fmt(r['expected_variable_total_minor'])}",
        f"- Projected balance before purchase: {_fmt(r['projected_balance_minor'])}",
        f"- After purchase: {_fmt(r['balance_after_purchase_minor'])} "
        f"(safety buffer {_fmt(r['safety_buffer_minor'])})",
    ]
    if not r["affordable"]:
        lines.append(f"You'd be {_fmt(r['shortfall_minor'])} short of the safety buffer.")
    return "\n".join(lines)


def _explain_savings(r: dict) -> str:
    if r["feasible"]:
        head = (
            f"Feasible. Save {_fmt(r['required_monthly_minor'])} per month for "
            f"{r['horizon_months']} months to reach {_fmt(r['goal_minor'])}; your "
            f"forecast monthly surplus is {_fmt(r['monthly_surplus_minor'])}."
        )
    else:
        head = (
            f"Honestly: not feasible as-is. The goal of {_fmt(r['goal_minor'])} needs "
            f"{_fmt(r['required_monthly_minor'])}/month but your forecast surplus is "
            f"{_fmt(r['monthly_surplus_minor'])}/month — a gap of {_fmt(r['gap_minor'])}."
        )
    lines = [head]
    if r["suggested_cuts"]:
        lines.append("Largest cuts that would close the gap:")
        for c in r["suggested_cuts"]:
            lines.append(
                f"- {c['category']}: cut {_fmt(c['suggested_cut_minor'])} of "
                f"{_fmt(c['current_monthly_minor'])}/month"
            )
    lines.append("Schedule:")
    for m in r["schedule"]:
        lines.append(
            f"- Month {m['month_index']}: save {_fmt(m['save_minor'])} "
            f"(total {_fmt(m['cumulative_saved_minor'])}, projected balance "
            f"{_fmt(m['projected_balance_minor'])})"
        )
    return "\n".join(lines)


def _explain_cashflow(r: dict) -> str:
    if "category_deltas" in r:  # month-over-month diagnosis
        direction = "dropped" if r["net_delta_minor"] < 0 else "improved"
        lines = [
            f"Net cashflow {direction} from {_fmt(r['net_a_minor'])} in {r['month_a']['year']}-"
            f"{r['month_a']['month']:02d} to {_fmt(r['net_b_minor'])} in {r['month_b']['year']}-"
            f"{r['month_b']['month']:02d} ({_fmt(r['net_delta_minor'])}).",
            f"Income change: {_fmt(r['income_delta_minor'])}; spending change: "
            f"{_fmt(r['expense_delta_minor'])}.",
            "Biggest category moves:",
        ]
        for d in r["category_deltas"][:5]:
            if d["delta_minor"] == 0:
                continue
            verb = "up" if d["delta_minor"] > 0 else "down"
            lines.append(
                f"- {d['category']}: {verb} {_fmt(abs(d['delta_minor']))} "
                f"({_fmt(d['amount_a_minor'])} → {_fmt(d['amount_b_minor'])})"
            )
        return "\n".join(lines)
    lines = [
        f"In {r['month']['year']}-{r['month']['month']:02d}: income {_fmt(r['income_minor'])}, "
        f"spending {_fmt(r['expense_minor'])}, net {_fmt(r['net_minor'])} "
        f"across {r['txn_count']} transactions.",
        "By category:",
    ]
    for cat, amount in sorted(r["by_category"].items(), key=lambda kv: -kv[1]):
        lines.append(f"- {cat}: {_fmt(amount)}")
    return "\n".join(lines)


def _explain_simulation(r: dict) -> str:
    impact = r["monthly_impact_minor"]
    verb = "improve" if impact >= 0 else "worsen"
    lines = [
        f"This scenario would {verb} your monthly net by {_fmt(abs(impact))} "
        f"({_fmt(r['baseline_monthly_net_minor'])} → {_fmt(r['scenario_monthly_net_minor'])}).",
    ]
    lines += [f"- {n}" for n in r.get("notes", [])]
    last = r["months"][-1]
    lines.append(
        f"After {r['horizon_months']} months your projected balance is "
        f"{_fmt(last['balance_after_minor'])} versus {_fmt(last['balance_before_minor'])} "
        f"without the change ({_fmt(last['delta_minor'])} difference)."
    )
    return "\n".join(lines)


def _explain_anomalies(r: dict) -> str:
    anomalies = r.get("anomalies", [])
    if not anomalies:
        return "No unusual transactions found in this window."
    lines = [f"Found {len(anomalies)} unusual transaction(s):"]
    for a in anomalies[:8]:
        lines.append(f"- {a['txn_date']} {a['merchant'] or '?'}: {a['reason']}")
    return "\n".join(lines)


def _explain_recurring(r: dict) -> str:
    groups = r.get("recurring", [])
    if not groups:
        return "No recurring payments detected yet — upload more history."
    lines = ["Detected recurring payments:"]
    for g in groups:
        flag = ""
        if g["price_change"]:
            flag = f"  ⚠ price changed {g['price_change_pct']:+.1f}%"
        lines.append(
            f"- {g['merchant']}: {_fmt(abs(g['typical_amount_minor']))} every "
            f"{g['cadence_days']} days ({g['occurrences']}×){flag}"
        )
    return "\n".join(lines)


def _explain_sql(r: dict) -> str:
    if r.get("error"):
        return f"That query was blocked for safety: {r['error']}"
    columns, rows = r.get("columns", []), r.get("rows", [])
    if not rows:
        return "No matching records."
    lines = [f"Found {len(rows)} row(s).", " | ".join(columns)]
    for row in rows[:15]:
        lines.append(" | ".join(str(v) for v in row))
    if len(rows) > 15:
        lines.append("…")
    return "\n".join(lines)


def _explain_doc_qa(r: dict) -> str:
    chunks = r.get("chunks", [])
    if not chunks:
        return "I couldn't find anything relevant in your uploaded documents."
    lines = ["Most relevant passages from your documents:"]
    for c in chunks[:3]:
        lines.append(f"- {c['text'][:300]}")
    return "\n".join(lines)


_TEMPLATES = {
    "affordability_tool": _explain_affordability,
    "savings_plan_tool": _explain_savings,
    "cashflow_tool": _explain_cashflow,
    "simulate_tool": _explain_simulation,
    "anomaly_tool": _explain_anomalies,
    "recurring_tool": _explain_recurring,
    "sql_tool": _explain_sql,
    "doc_qa_tool": _explain_doc_qa,
}


def explain_template(tool: str, output: dict) -> str:
    result = output["result"]
    if isinstance(result, dict) and result.get("error") and tool != "sql_tool":
        body = f"I couldn't complete that: {result['error']}"
    else:
        body = _TEMPLATES[tool](result)
    warnings = output.get("warnings") or []
    if warnings:
        body += "\n\n⚠ " + " ".join(warnings)
    return body


def explain(message: str, intent: str, tool: str, output: dict) -> tuple[str, bool]:
    """Returns (answer, guardrail_passed_via_llm). Falls back to the template
    whenever the LLM is unavailable or keeps inventing numbers."""
    prompt = _PROMPT.format(
        message=message,
        intent=intent,
        tool=tool,
        result=json.dumps(output, default=str),
    )
    for attempt in range(2):
        raw = complete(prompt, smart=True)
        if raw is None:
            break
        violations = find_violations(raw, [output])
        if not violations:
            return raw.strip(), True
        prompt += (
            f"\n\nYour previous answer contained numbers not present in the tool "
            f"result: {violations}. Rewrite using only numbers from the JSON."
        )
    return explain_template(tool, output), False
