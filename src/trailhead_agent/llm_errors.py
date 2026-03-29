"""Map vendor SDK exceptions to user-actionable LLMProviderError messages."""

from __future__ import annotations

from trailhead_agent.errors import LLMProviderError


def raise_mapped_llm_error(provider: str, exc: Exception) -> None:
    """Raise LLMProviderError with rate-limit / quota hints when detectable."""
    raw = str(exc)
    lower = raw.lower()
    if (
        "429" in raw
        or "resource_exhausted" in lower
        or "too many requests" in lower
        or "rate_limit" in lower
        or "quota" in lower and "exceed" in lower
    ):
        raise LLMProviderError(
            f"{provider}: rate limit or quota exceeded (429). "
            "Wait 30–60 seconds, try a different model (e.g. GEMINI_MODEL=gemini-2.5-flash), "
            "or review billing and limits: https://ai.google.dev/gemini-api/docs/rate-limits "
            f"(OpenAI: https://platform.openai.com/docs/guides/rate-limits). Raw: {raw[:900]}"
        ) from exc
    raise LLMProviderError(f"{provider} request failed: {exc}") from exc
