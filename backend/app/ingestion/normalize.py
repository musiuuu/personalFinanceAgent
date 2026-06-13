"""Merchant cleaning, money parsing, sign convention, dedup hashing."""
import hashlib
import re
from decimal import Decimal, InvalidOperation

# Known messy-prefix → clean merchant mappings (extend freely).
KNOWN_MERCHANTS: dict[str, str] = {
    "CAREEM": "CAREEM",
    "UBER": "UBER",
    "FOODPANDA": "FOODPANDA",
    "NETFLIX": "NETFLIX",
    "SPOTIFY": "SPOTIFY",
    "DARAZ": "DARAZ",
    "IMTIAZ": "IMTIAZ",
    "CARREFOUR": "CARREFOUR",
    "METRO": "METRO",
    "ALFATAH": "ALFATAH",
    "K-ELECTRIC": "K-ELECTRIC",
    "KE BILL": "K-ELECTRIC",
    "SSGC": "SSGC",
    "PTCL": "PTCL",
    "JAZZ": "JAZZ",
    "ZONG": "ZONG",
    "MCDONALD": "MCDONALDS",
    "KFC": "KFC",
    "PSO": "PSO",
    "SHELL": "SHELL",
    "TOTAL PARCO": "TOTAL PARCO",
    "AMAZON": "AMAZON",
    "ALIEXPRESS": "ALIEXPRESS",
}

_NOISE_PATTERNS = [
    re.compile(r"\bPOS\s*\d*\b", re.I),
    re.compile(r"\bREF[*#:\-]?\s*\w+\b", re.I),
    re.compile(r"\bTXN[*#:\-]?\s*\w+\b", re.I),
    re.compile(r"\bAUTH[*#:\-]?\s*\w+\b", re.I),
    re.compile(r"\bCARD\s*\d+\b", re.I),
    re.compile(r"\*+\d+"),
    re.compile(r"\b\d{6,}\b"),  # long reference numbers
    re.compile(r"\b\d{2}[/-]\d{2}(?:[/-]\d{2,4})?\b"),  # embedded dates
]


def clean_merchant(raw_description: str) -> str:
    """Strip transaction-reference noise and map known patterns."""
    s = raw_description.upper()
    for known, clean in KNOWN_MERCHANTS.items():
        if known in s:
            return clean
    for pat in _NOISE_PATTERNS:
        s = pat.sub(" ", s)
    s = re.sub(r"[^A-Z0-9&.\- ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -.*")
    return s or raw_description.upper().strip()


def parse_money_minor(value: str | float | int | None) -> int | None:
    """'250,000.00' / '(1,500.00)' / '1500 Dr' → signed integer minor units.

    Parentheses and a 'Dr' suffix mean negative; 'Cr' positive. Returns None
    for blanks/dashes.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value * 100
    if isinstance(value, float):
        return round(value * 100)
    s = str(value).strip()
    if s in ("", "-", "--", "N/A"):
        return None
    sign = 1
    if s.startswith("(") and s.endswith(")"):
        sign, s = -1, s[1:-1]
    upper = s.upper()
    if upper.endswith("DR"):
        sign, s = -1, s[:-2]
    elif upper.endswith("CR"):
        s = s[:-2]
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-", "."):
        return None
    try:
        return sign * int((Decimal(s) * 100).to_integral_value())
    except InvalidOperation:
        return None


def dedup_hash(account_id: int, txn_date, amount_minor: int, raw_description: str) -> str:
    payload = f"{account_id}|{txn_date.isoformat()}|{amount_minor}|{raw_description.strip().lower()}"
    return hashlib.sha256(payload.encode()).hexdigest()
