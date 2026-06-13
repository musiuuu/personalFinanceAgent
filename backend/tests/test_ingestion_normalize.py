from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from app.ingestion.normalize import clean_merchant, dedup_hash, parse_money_minor
from app.ingestion.pdf_text_parser import parse_statement_text


def test_clean_merchant_strips_noise():
    assert clean_merchant("NETFLIX.COM POS 4521") == "NETFLIX"
    assert clean_merchant("CAREEM*RIDES REF*X1") == "CAREEM"
    assert clean_merchant("FOODPANDA ORDER TXN 99812") == "FOODPANDA"
    assert clean_merchant("GOLD SOUK JEWELLERY") == "GOLD SOUK JEWELLERY"
    assert clean_merchant("RENT TRANSFER IBFT OUT REF1000") == "RENT TRANSFER IBFT OUT"


def test_parse_money_minor():
    assert parse_money_minor("250,000.00") == 250_000_00
    assert parse_money_minor("(1,500.00)") == -1_500_00
    assert parse_money_minor("1,500.00 Dr") == -1_500_00
    assert parse_money_minor("1,500.00 Cr") == 1_500_00
    assert parse_money_minor("-42.50") == -42_50
    assert parse_money_minor("") is None
    assert parse_money_minor("-") is None
    assert parse_money_minor(None) is None


def test_dedup_hash_stability_and_sensitivity():
    d = date(2026, 1, 5)
    h1 = dedup_hash(1, d, -2000_00, "NETFLIX.COM POS 4521")
    h2 = dedup_hash(1, d, -2000_00, "  netflix.com pos 4521 ")  # case/space-insensitive
    h3 = dedup_hash(1, d, -2100_00, "NETFLIX.COM POS 4521")
    h4 = dedup_hash(2, d, -2000_00, "NETFLIX.COM POS 4521")
    assert h1 == h2
    assert h1 != h3
    assert h1 != h4


@given(
    account_id=st.integers(min_value=1, max_value=10),
    amount=st.integers(min_value=-10**9, max_value=10**9),
    desc=st.text(min_size=1, max_size=40),
)
def test_dedup_hash_is_deterministic(account_id, amount, desc):
    d = date(2026, 1, 1)
    assert dedup_hash(account_id, d, amount, desc) == dedup_hash(
        account_id, d, amount, desc
    )


def test_pdf_statement_text_lines_parse():
    """The text-line parser (shared by pdf_text and OCR paths) recovers dates,
    signed amounts and balances from a plain statement dump."""
    text = """
HBL  STATEMENT OF ACCOUNT
Opening Balance: 100,000.00
01-Jan-2026  SALARY ACME CORP PAYROLL        250,000.00   350,000.00
03-Jan-2026  RENT TRANSFER REF991             60,000.00   290,000.00
05-Jan-2026  NETFLIX.COM POS 4521              2,000.00   288,000.00
Closing Balance: 288,000.00
"""
    statement = parse_statement_text(text)
    assert [r.amount_minor for r in statement.rows] == [
        250_000_00, -60_000_00, -2_000_00
    ]
    assert statement.opening_balance_minor == 100_000_00
    assert statement.closing_balance_minor == 288_000_00
    # And it reconciles.
    total = sum(r.amount_minor for r in statement.rows)
    assert statement.opening_balance_minor + total == statement.closing_balance_minor
