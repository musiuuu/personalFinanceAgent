from app.agent.guardrail import collect_allowed_numbers, find_violations


def test_minor_units_allow_pkr_renderings():
    allowed = collect_allowed_numbers({"purchase_minor": 25_000_000})
    assert 25_000_000.0 in allowed  # raw paisa
    assert 250_000.0 in allowed  # PKR


def test_clean_prose_passes():
    result = {
        "result": {
            "affordable": False,
            "purchase_minor": 25_000_000,
            "projected_balance_minor": 23_800_000,
            "shortfall_minor": 6_200_000,
            "target_date": "2026-05-01",
        }
    }
    prose = (
        "Not safely. Buying for PKR 250,000 by 2026-05-01 would leave you "
        "PKR 62,000 short; your projected balance is PKR 238,000."
    )
    assert find_violations(prose, [result]) == []


def test_invented_number_is_caught():
    result = {"result": {"net_minor": 14_300_000}}
    prose = "Your net was PKR 143,000 and you spent PKR 87,500 on dining."
    assert find_violations(prose, [result]) == [87_500.0]


def test_comma_formatting_and_rounding_tolerated():
    result = {"result": {"amount_minor": 123_456}}  # PKR 1,234.56
    assert find_violations("That cost PKR 1,234.56.", [result]) == []
    assert find_violations("That cost about PKR 1,235.", [result]) == []
    assert find_violations("That cost PKR 1,290.", [result]) == [1290.0]


def test_small_counts_and_years_are_free():
    result = {"result": {"x_minor": 100_00}}
    prose = "Over 3 months in 2026, across 12 transactions: PKR 100 each."
    assert find_violations(prose, [result]) == []


def test_numbers_inside_result_strings_are_allowed():
    result = {
        "result": {"notes": ["Cut DINING by 30% (-300000 minor/month)"]},
    }
    assert find_violations("That trims 30% — PKR 3,000 a month.", [result]) == []
