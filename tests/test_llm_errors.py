import pytest

from trailhead_agent.errors import LLMProviderError
from trailhead_agent.llm_errors import raise_mapped_llm_error


def test_rate_limit_message_includes_hint():
    with pytest.raises(LLMProviderError, match="rate limit or quota"):
        raise_mapped_llm_error("Gemini", Exception("429 RESOURCE_EXHAUSTED"))


def test_generic_wrapped():
    with pytest.raises(LLMProviderError, match="OpenAI request failed"):
        raise_mapped_llm_error("OpenAI", ValueError("bad"))
