"""Thin Anthropic wrapper. Returns None when no API key is configured so
every caller falls back to its deterministic path."""
from ..config import get_settings


def complete(prompt: str, smart: bool = False, max_tokens: int = 700) -> str | None:
    settings = get_settings()
    if not settings.llm_enabled:
        return None
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.llm_smart_model if smart else settings.llm_cheap_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
