"""Generate synthetic PKR bank statements for the demo.

Deterministic by construction: running balances are computed while writing,
so every generated statement reconciles exactly (opening + sum == closing).
Run:  python sample_data/generate.py
"""
import csv
from datetime import date
from pathlib import Path

OUT = Path(__file__).parent

# (day-offset-within-month, description, amount in PKR; negative = outflow)
# Six months: Jan–Jun 2026. Story baked in:
#   - ACME salary +260k monthly
#   - rent 65k, Netflix 2k (price rises to 2.6k in May = price-change insight)
#   - groceries/dining/transport/fuel vary month to month
#   - one-off anomalies: gold jewellery in March, duplicate FOODPANDA in April
MONTHS = [(2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6)]

BASE = [
    (1, "SALARY ACME CORP PAYROLL", 260_000),
    (3, "RENT TRANSFER IBFT OUT REF{ref}", -65_000),
    (5, "NETFLIX.COM POS 4521", -2_000),
    (6, "SPOTIFY P*ABC123", -1_000),
    (8, "K-ELECTRIC BILL CONSUMER 882", -12_000),
    (9, "PTCL BROADBAND BILL", -3_500),
]

VARIABLE = {
    # month index → extra (day, description, amount) rows
    0: [
        (10, "IMTIAZ SUPER MARKET POS 1102", -28_000),
        (15, "FOODPANDA ORDER TXN 99812", -4_500),
        (18, "CAREEM RIDES REF*X1", -3_000),
        (22, "PSO FUEL STATION", -8_000),
        (25, "DARAZ.PK ORDER 776", -6_500),
    ],
    1: [
        (10, "IMTIAZ SUPER MARKET POS 1102", -31_000),
        (14, "FOODPANDA ORDER TXN 10221", -6_000),
        (19, "CAREEM RIDES REF*X2", -2_500),
        (23, "PSO FUEL STATION", -7_500),
        (26, "CINEPAX CINEMA", -2_400),
    ],
    2: [
        (9, "IMTIAZ SUPER MARKET POS 1102", -27_500),
        (12, "FOODPANDA ORDER TXN 11456", -5_200),
        (16, "GOLD SOUK JEWELLERY", -90_000),  # anomaly: new large merchant
        (20, "CAREEM RIDES REF*X3", -3_200),
        (24, "SHELL PETROL", -8_200),
    ],
    3: [
        (8, "IMTIAZ SUPER MARKET POS 1102", -29_500),
        (13, "FOODPANDA ORDER TXN 12001", -4_800),
        (13, "FOODPANDA ORDER TXN 12001B", -4_800),  # anomaly: duplicate charge
        (18, "CAREEM RIDES REF*X4", -2_800),
        (22, "PSO FUEL STATION", -7_800),
        (27, "AGHA KHAN HOSPITAL LAB", -9_000),
    ],
    4: [
        (10, "IMTIAZ SUPER MARKET POS 1102", -30_500),
        (15, "FOODPANDA ORDER TXN 13310", -5_500),
        (19, "CAREEM RIDES REF*X5", -3_100),
        (23, "TOTAL PARCO FUEL", -7_900),
        (28, "KHAADI CLOTHING", -12_000),
    ],
    5: [
        (9, "IMTIAZ SUPER MARKET POS 1102", -29_000),
        (14, "FOODPANDA ORDER TXN 14102", -5_000),
        (18, "CAREEM RIDES REF*X6", -2_900),
        (22, "PSO FUEL STATION", -8_100),
        (26, "ATM CASH WITHDRAWAL CARD 5566", -20_000),
    ],
}

# Netflix price change from May (month index 4) onward.
NETFLIX_NEW_PRICE = -2_600


def month_rows(idx: int, year: int, month: int):
    rows = []
    for day, desc, amount in BASE:
        if "NETFLIX" in desc and idx >= 4:
            amount = NETFLIX_NEW_PRICE
        rows.append((date(year, month, day), desc.format(ref=1000 + idx), amount))
    for day, desc, amount in VARIABLE[idx]:
        rows.append((date(year, month, day), desc, amount))
    rows.sort(key=lambda r: r[0])
    return rows


def fmt(amount_pkr: int) -> str:
    return f"{amount_pkr:,.2f}"


def write_hbl(months: list[int], opening_pkr: int, filename: str):
    """HBL layout: Date | Value Date | Particulars | Chq No | Debit | Credit | Balance."""
    balance = opening_pkr
    out = OUT / filename
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Account Title:", "Demo User"])
        w.writerow(["Account No:", "PK00HABB0000000012345678"])
        w.writerow(["Opening Balance:", fmt(opening_pkr)])
        w.writerow([])
        w.writerow(["Date", "Value Date", "Particulars", "Chq No", "Debit", "Credit", "Balance"])
        for idx in months:
            y, m = MONTHS[idx]
            for d, desc, amount in month_rows(idx, y, m):
                balance += amount
                w.writerow([
                    d.strftime("%d-%b-%Y"),
                    d.strftime("%d-%b-%Y"),
                    desc,
                    "",
                    fmt(-amount) if amount < 0 else "",
                    fmt(amount) if amount > 0 else "",
                    fmt(balance),
                ])
        w.writerow([])
        w.writerow(["Closing Balance:", fmt(balance)])
    print(f"wrote {out.name}  (closing {fmt(balance)})")
    return balance


def write_meezan(months: list[int], opening_pkr: int, filename: str):
    """Meezan layout: Transaction Date | Description | Withdrawal | Deposit | Balance."""
    balance = opening_pkr
    out = OUT / filename
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Statement of Account"])
        w.writerow(["Opening Balance:", fmt(opening_pkr)])
        w.writerow(["Transaction Date", "Description", "Withdrawal Amount", "Deposit Amount", "Available Balance"])
        for idx in months:
            y, m = MONTHS[idx]
            for d, desc, amount in month_rows(idx, y, m):
                balance += amount
                w.writerow([
                    d.strftime("%d/%m/%Y"),
                    desc,
                    fmt(-amount) if amount < 0 else "",
                    fmt(amount) if amount > 0 else "",
                    fmt(balance),
                ])
        w.writerow(["Closing Balance:", fmt(balance)])
    print(f"wrote {out.name}  (closing {fmt(balance)})")
    return balance


if __name__ == "__main__":
    # One continuous HBL account across all six months, split over two
    # statements so re-upload/dedup and multi-statement flows can be demoed.
    closing_q1 = write_hbl([0, 1, 2], 150_000, "hbl_statement_2026_q1.csv")
    write_hbl([3, 4, 5], closing_q1, "hbl_statement_2026_q2.csv")
    # A Meezan-format statement of the same months for adapter demos.
    write_meezan([4, 5], 150_000, "meezan_statement_may_jun_2026.csv")
