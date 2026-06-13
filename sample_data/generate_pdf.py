"""Generate a text-based PDF statement for the demo.

This produces a PDF with a real text layer (not a scanned image), so the
text-PDF ingestion path handles it with no OCR. Balances are written while
iterating, so the statement reconciles by construction.

Reuses the transaction data from generate.py so the PDF tells the same story
as the CSV statements.

Run:  python sample_data/generate_pdf.py   (needs fpdf2: pip install fpdf2)
"""
from pathlib import Path

from fpdf import FPDF

from generate import MONTHS, fmt, month_rows

OUT = Path(__file__).parent


def build(months_idx: list[int], opening_pkr: int, filename: str) -> int:
    lines: list[str] = [
        "HBL  -  STATEMENT OF ACCOUNT",
        "Account Title: Demo User",
        "Account No: PK00HABB0000000012345678",
        "",
        f"Opening Balance: {fmt(opening_pkr)}",
        "",
        f"{'Date':<13}{'Particulars':<38}{'Amount':>14}{'Balance':>16}",
    ]
    balance = opening_pkr
    for idx in months_idx:
        y, m = MONTHS[idx]
        for d, desc, amount in month_rows(idx, y, m):
            balance += amount
            date_s = d.strftime("%d-%b-%Y")
            desc_s = desc[:36]
            lines.append(f"{date_s:<13}{desc_s:<38}{fmt(-amount):>14}{fmt(balance):>16}")
    lines.append("")
    lines.append(f"Closing Balance: {fmt(balance)}")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Courier", size=9)
    for line in lines:
        pdf.cell(0, 5, text=line, new_x="LMARGIN", new_y="NEXT")
    out = OUT / filename
    pdf.output(str(out))
    print(f"wrote {out.name}  (closing {fmt(balance)})")
    return balance


if __name__ == "__main__":
    # Same three months and opening as the q1 CSV → closing 446,000.
    build([0, 1, 2], 150_000, "hbl_statement_2026_q1.pdf")
