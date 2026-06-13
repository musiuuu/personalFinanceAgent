"""Deterministic extraction of money amounts, horizons and dates from user
text. Used by the heuristic planner (offline fallback) and to sanity-check
LLM-extracted arguments.
"""
import re
from datetime import date

from dateutil.relativedelta import relativedelta

_AMOUNT_RE = re.compile(
    r"(?:pkr|rs\.?|rupees)?\s*([\d][\d,]*(?:\.\d+)?)\s*(k|thousand|lac|lakh|lacs|lakhs|crore|m|million)?",
    re.I,
)
_MULTIPLIERS = {
    None: 1,
    "k": 1_000,
    "thousand": 1_000,
    "lac": 100_000,
    "lakh": 100_000,
    "lacs": 100_000,
    "lakhs": 100_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "crore": 10_000_000,
}


def parse_amounts_pkr_minor(text: str) -> list[int]:
    """All money-looking figures in the text, largest-context first, in paisa."""
    amounts = []
    for m in _AMOUNT_RE.finditer(text):
        number = float(m.group(1).replace(",", ""))
        unit = (m.group(2) or "").lower() or None
        amounts.append(int(round(number * _MULTIPLIERS[unit] * 100)))
    return amounts


def parse_horizon_months(text: str, default: int | None = None) -> int | None:
    """'3-month plan', 'in 4 months', 'over six months' → months."""
    words = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    }
    if m := re.search(r"(\d{1,2})[\s-]*month", text, re.I):
        return int(m.group(1))
    if m := re.search(r"\b(" + "|".join(words) + r")[\s-]*month", text, re.I):
        return words[m.group(1).lower()]
    if re.search(r"\bnext\s+month\b", text, re.I):
        return 1
    if m := re.search(r"(\d{1,2})[\s-]*year", text, re.I):
        return int(m.group(1)) * 12
    return default


def parse_target_date(text: str, as_of: date) -> date:
    """'next month', 'in N months', month names → a concrete date.
    Defaults to one month out."""
    months = parse_horizon_months(text)
    if months is not None:
        return as_of + relativedelta(months=months)
    month_names = [
        "january", "february", "march", "april", "may", "june", "july",
        "august", "september", "october", "november", "december",
    ]
    lowered = text.lower()
    for i, name in enumerate(month_names, start=1):
        if name in lowered or f" {name[:3]} " in f" {lowered} ":
            year = as_of.year + (1 if i < as_of.month else 0)
            return date(year, i, 1)
    return as_of + relativedelta(months=1)


def parse_percentage(text: str) -> float | None:
    if m := re.search(r"(\d{1,3}(?:\.\d+)?)\s*(?:%|percent)", text, re.I):
        return float(m.group(1))
    return None
