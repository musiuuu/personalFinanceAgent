"""LLM categorization for merchants the rules table doesn't know.

The model maps a merchant string onto the FIXED taxonomy — it may never invent
a category. Anything unparseable or off-taxonomy degrades to OTHER. Calls are
batched per unknown merchant and cached in the DB, so each merchant is paid
for at most once. Without an API key this module is never called.
"""
from ..config import get_settings
from ..models import Category

_PROMPT = """Classify this bank-statement merchant/description into exactly one category.

Merchant: {merchant}

Allowed categories (respond with one of these tokens and nothing else):
{categories}

Rules:
- Pick the single best fit.
- If genuinely unclassifiable, respond OTHER.
- Respond with the category token only."""


def categorize_with_llm(merchant: str) -> Category:
    settings = get_settings()
    if not settings.llm_enabled:
        return Category.OTHER

    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_cheap_model,
        max_tokens=16,
        messages=[
            {
                "role": "user",
                "content": _PROMPT.format(
                    merchant=merchant,
                    categories=", ".join(c.value for c in Category),
                ),
            }
        ],
    )
    raw = response.content[0].text.strip().upper()
    try:
        return Category(raw)
    except ValueError:
        return Category.OTHER
