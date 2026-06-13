"""Intent classification: LLM when available, keyword heuristics otherwise.
The heuristic path also serves as the offline/demo mode and the test target.
"""
import re

from .llm import complete

INTENTS = [
    "AFFORDABILITY",
    "DIAGNOSIS",
    "PLANNING",
    "SIMULATION",
    "SQL_QUERY",
    "DOC_QA",
    "SMALLTALK",
]

_PROMPT = """Classify this personal-finance question into exactly one intent.

Intents:
- AFFORDABILITY: can the user afford a specific purchase ("can I afford X", "is X within reach")
- DIAGNOSIS: why/where questions about past spending ("where am I overspending", "why did cashflow drop")
- PLANNING: building a savings plan toward a goal ("save 300k in 3 months")
- SIMULATION: hypothetical changes ("what if I cancel Netflix", "if I cut dining 30%")
- SQL_QUERY: a factual lookup over transactions ("how much did I spend on groceries in March", "list charges over 10k")
- DOC_QA: about an uploaded document's content ("what were the invoice terms")
- SMALLTALK: greetings or anything that needs no data

Question: {message}

Respond with the intent token only."""


def classify_heuristic(message: str) -> str:
    m = message.lower()
    if re.search(r"\bwhat[\s-]*if\b|\bif i (cancel|cut|drop|stop|reduce)|simulat", m):
        return "SIMULATION"
    if re.search(r"afford|within (my )?reach|enough (money|balance) (for|to buy)", m):
        return "AFFORDABILITY"
    if re.search(r"sav(e|ing|ings) plan|plan to save|save .*\b(in|over|by)\b|reach .* goal", m):
        return "PLANNING"
    if re.search(
        r"\bwhy\b|\bwhere am i\b|overspend|drop(ped)?|decreas|went (up|down)|compare|"
        r"anomal|unusual|suspicious|weird charge", m,
    ):
        return "DIAGNOSIS"
    if re.search(r"invoice|document|terms|warranty|contract|receipt says", m):
        return "DOC_QA"
    if re.search(
        r"how much|how many|list|show( me)?|total|sum|average|spent|spend|largest|"
        r"biggest|top \d|transactions?\b", m,
    ):
        return "SQL_QUERY"
    if re.search(r"^\s*(hi|hello|hey|salam|thanks|thank you)\b", m):
        return "SMALLTALK"
    return "SQL_QUERY"  # safe default: factual lookup


def classify(message: str) -> str:
    raw = complete(_PROMPT.format(message=message), smart=False, max_tokens=12)
    if raw is not None:
        candidate = raw.strip().upper()
        if candidate in INTENTS:
            return candidate
    return classify_heuristic(message)
