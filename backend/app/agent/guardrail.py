"""The hallucination trap (spec Section 8.4).

Every number the explainer emits must already exist in the tool result —
either verbatim, or as the PKR rendering of a minor-units figure (value/100).
If the explainer invents a figure, the caller regenerates once and then falls
back to a deterministic template. Cheap, and it makes 'the model made up a
number' structurally impossible in the final answer.
"""
import re
from typing import Any

_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Small integers show up in prose as counts/ordinals ("3 months", "month 2",
# "top 5") and in dates; they carry no financial information worth guarding.
_FREE_INTS = set(range(0, 32)) | {100}
_FREE_YEARS = set(range(2000, 2101))


def _add_number(allowed: set[float], v: float) -> None:
    for candidate in (v, -v, abs(v)):
        allowed.add(round(candidate, 4))
    # Minor units → PKR renderings.
    allowed.add(round(v / 100, 4))
    allowed.add(round(abs(v) / 100, 4))
    allowed.add(float(round(abs(v) / 100)))


def collect_allowed_numbers(obj: Any, allowed: set[float] | None = None) -> set[float]:
    if allowed is None:
        allowed = set()
    if isinstance(obj, bool):
        return allowed
    if isinstance(obj, (int, float)):
        _add_number(allowed, float(obj))
    elif isinstance(obj, str):
        for m in _NUMBER_RE.finditer(obj):
            _add_number(allowed, float(m.group(0).replace(",", "")))
    elif isinstance(obj, dict):
        for v in obj.values():
            collect_allowed_numbers(v, allowed)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            collect_allowed_numbers(v, allowed)
    return allowed


def extract_numbers(prose: str) -> list[float]:
    return [float(m.group(0).replace(",", "")) for m in _NUMBER_RE.finditer(prose)]


def find_violations(prose: str, tool_results: list[dict]) -> list[float]:
    """Numbers in the prose that appear in no tool result."""
    allowed: set[float] = set()
    for result in tool_results:
        collect_allowed_numbers(result, allowed)

    violations = []
    for n in extract_numbers(prose):
        if n in _FREE_INTS or n in _FREE_YEARS:
            continue
        rounded = round(n, 4)
        if rounded in allowed:
            continue
        # Tolerate rounding to whole rupees (e.g. 1,234.56 → "PKR 1,235").
        if any(abs(rounded - a) <= 0.51 for a in allowed):
            continue
        violations.append(n)
    return violations
