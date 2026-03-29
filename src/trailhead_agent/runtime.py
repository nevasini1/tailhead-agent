from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMRetrySettings:
    max_attempts: int
    min_wait_s: float
    max_wait_s: float


def llm_retry_settings() -> LLMRetrySettings:
    try:
        n = int(os.environ.get("LLM_MAX_RETRIES", "4"))
        n = max(1, min(n, 10))
    except ValueError:
        n = 4
    try:
        mn = float(os.environ.get("LLM_RETRY_MIN_WAIT_S", "1"))
        mx = float(os.environ.get("LLM_RETRY_MAX_WAIT_S", "30"))
    except ValueError:
        mn, mx = 1.0, 30.0
    return LLMRetrySettings(max_attempts=n, min_wait_s=mn, max_wait_s=max(mx, mn))
