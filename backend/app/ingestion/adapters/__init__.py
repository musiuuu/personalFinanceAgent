from .base import BankAdapter
from .generic import GenericAdapter
from .hbl import HBLAdapter
from .meezan import MeezanAdapter

# Order matters: specific bank signatures first, generic heuristic last.
ADAPTERS: list[BankAdapter] = [HBLAdapter(), MeezanAdapter(), GenericAdapter()]


def pick_adapter(headers: list[str]) -> BankAdapter:
    for adapter in ADAPTERS:
        if adapter.matches(headers):
            return adapter
    return ADAPTERS[-1]
