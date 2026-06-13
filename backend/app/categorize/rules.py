"""Deterministic keyword → category lookup. First line of categorization;
free, instant, and auditable. The LLM only ever sees merchants that miss here.
"""
from ..models import Category

# Substring (uppercase) → category. Order matters: first hit wins, so put the
# most specific patterns first. Needles with surrounding spaces are
# word-boundary matches (the haystack is padded with spaces before matching).
RULES: list[tuple[str, Category]] = [
    # income
    ("SALARY", Category.SALARY),
    ("PAYROLL", Category.SALARY),
    # housing — must outrank transfer keywords ("RENT TRANSFER IBFT OUT" is
    # rent, not a generic transfer); word-bounded so CURRENT doesn't match
    (" RENT ", Category.RENT),
    # transfers
    ("IBFT IN", Category.TRANSFER_IN),
    ("FUNDS RECEIVED", Category.TRANSFER_IN),
    ("IBFT OUT", Category.TRANSFER_OUT),
    ("FUNDS TRANSFER", Category.TRANSFER_OUT),
    ("RAAST", Category.TRANSFER_OUT),
    # utilities
    ("K-ELECTRIC", Category.UTILITIES),
    ("KE BILL", Category.UTILITIES),
    ("SSGC", Category.UTILITIES),
    ("SNGPL", Category.UTILITIES),
    ("PTCL", Category.UTILITIES),
    ("WASA", Category.UTILITIES),
    ("JAZZ", Category.UTILITIES),
    ("ZONG", Category.UTILITIES),
    ("TELENOR", Category.UTILITIES),
    ("UFONE", Category.UTILITIES),
    ("STORMFIBER", Category.UTILITIES),
    ("NAYATEL", Category.UTILITIES),
    # groceries
    ("IMTIAZ", Category.GROCERIES),
    ("CARREFOUR", Category.GROCERIES),
    ("METRO", Category.GROCERIES),
    ("ALFATAH", Category.GROCERIES),
    ("CHASE UP", Category.GROCERIES),
    ("SPAR", Category.GROCERIES),
    ("GROCER", Category.GROCERIES),
    ("MART", Category.GROCERIES),
    # dining
    ("FOODPANDA", Category.DINING),
    ("MCDONALDS", Category.DINING),
    ("MCDONALD", Category.DINING),
    ("KFC", Category.DINING),
    ("PIZZA", Category.DINING),
    ("RESTAURANT", Category.DINING),
    ("CAFE", Category.DINING),
    ("BIRYANI", Category.DINING),
    ("HARDEES", Category.DINING),
    ("SUBWAY", Category.DINING),
    # transport & fuel
    ("CAREEM", Category.TRANSPORT),
    ("UBER", Category.TRANSPORT),
    ("BYKEA", Category.TRANSPORT),
    ("INDRIVE", Category.TRANSPORT),
    ("PSO", Category.FUEL),
    ("SHELL", Category.FUEL),
    ("TOTAL PARCO", Category.FUEL),
    ("ATTOCK PETROL", Category.FUEL),
    ("PETROL", Category.FUEL),
    ("FUEL", Category.FUEL),
    # subscriptions
    ("NETFLIX", Category.SUBSCRIPTIONS),
    ("SPOTIFY", Category.SUBSCRIPTIONS),
    ("YOUTUBE PREMIUM", Category.SUBSCRIPTIONS),
    ("ICLOUD", Category.SUBSCRIPTIONS),
    ("APPLE.COM", Category.SUBSCRIPTIONS),
    ("GOOGLE ONE", Category.SUBSCRIPTIONS),
    ("DISNEY", Category.SUBSCRIPTIONS),
    ("TAMASHA", Category.SUBSCRIPTIONS),
    # shopping
    ("DARAZ", Category.SHOPPING),
    ("AMAZON", Category.SHOPPING),
    ("ALIEXPRESS", Category.SHOPPING),
    ("KHAADI", Category.SHOPPING),
    ("GUL AHMED", Category.SHOPPING),
    ("OUTFITTERS", Category.SHOPPING),
    # health & education
    ("PHARMACY", Category.HEALTH),
    ("HOSPITAL", Category.HEALTH),
    ("CLINIC", Category.HEALTH),
    ("LAB ", Category.HEALTH),
    ("UNIVERSITY", Category.EDUCATION),
    ("SCHOOL FEE", Category.EDUCATION),
    ("TUITION", Category.EDUCATION),
    ("COURSERA", Category.EDUCATION),
    ("UDEMY", Category.EDUCATION),
    # travel & entertainment
    ("AIRLINE", Category.TRAVEL),
    ("PIA", Category.TRAVEL),
    ("AIRBLUE", Category.TRAVEL),
    ("SERENA", Category.TRAVEL),
    ("HOTEL", Category.TRAVEL),
    ("BOOKING.COM", Category.TRAVEL),
    ("CINEMA", Category.ENTERTAINMENT),
    ("CINEPAX", Category.ENTERTAINMENT),
    ("STEAM", Category.ENTERTAINMENT),
    ("PLAYSTATION", Category.ENTERTAINMENT),
    # fees & cash
    ("BANK CHARGES", Category.FEES_CHARGES),
    ("SERVICE CHARGE", Category.FEES_CHARGES),
    ("SMS ALERT", Category.FEES_CHARGES),
    ("ANNUAL FEE", Category.FEES_CHARGES),
    ("FED ", Category.FEES_CHARGES),
    ("WHT", Category.FEES_CHARGES),
    ("ATM", Category.CASH_WITHDRAWAL),
    ("CASH WITHDRAWAL", Category.CASH_WITHDRAWAL),
]


def categorize_by_rules(merchant_or_description: str) -> Category | None:
    padded = f" {merchant_or_description.upper()} "
    for needle, category in RULES:
        if needle in padded:
            return category
    return None
