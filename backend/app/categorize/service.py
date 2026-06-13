"""Categorization pipeline: rules → cache → LLM → OTHER.

Deterministic rules always win. The cache means the LLM sees each unknown
merchant once, ever.
"""
from sqlmodel import Session, select

from ..config import get_settings
from ..models import Category, MerchantCategoryCache
from .llm_fallback import categorize_with_llm
from .rules import categorize_by_rules


def categorize(
    session: Session, merchant_normalized: str, raw_description: str = ""
) -> Category:
    by_rule = categorize_by_rules(merchant_normalized) or (
        categorize_by_rules(raw_description) if raw_description else None
    )
    if by_rule is not None:
        return by_rule

    cached = session.exec(
        select(MerchantCategoryCache).where(
            MerchantCategoryCache.merchant_normalized == merchant_normalized
        )
    ).first()
    if cached is not None:
        try:
            return Category(cached.category)
        except ValueError:
            return Category.OTHER

    # Don't poison the cache with OTHER when the LLM isn't configured — the
    # merchant should get a real classification once a key is provided.
    if not get_settings().llm_enabled:
        return Category.OTHER

    category = categorize_with_llm(merchant_normalized)
    session.add(
        MerchantCategoryCache(
            merchant_normalized=merchant_normalized, category=category.value
        )
    )
    return category
