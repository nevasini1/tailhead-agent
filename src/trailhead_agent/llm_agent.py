from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, TypeVar

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from trailhead_agent.errors import LLMProviderError
from trailhead_agent.llm_errors import raise_mapped_llm_error
from trailhead_agent.llm_schemas import (
    LLMRankingResponse,
    materialize_ordered_units,
    openai_ranking_json_schema,
    try_parse_planner_dict,
    try_parse_ranking_dict,
)
from trailhead_agent.models import UnitRef
from trailhead_agent.ranking_graph import run_ranking_graph
from trailhead_agent.runtime import llm_retry_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


def ranking_user_message_context(*, candidate_count: int) -> dict[str, Any]:
    """Structured instructions merged into the user JSON (primary rank + repair)."""
    return {
        "meta": {
            "candidate_count": candidate_count,
            "deliverable": "Single JSON object: keys ordered_units and excluded only.",
        },
        "execution_steps": [
            "Read INTENT: extract goals, must-haves, avoid-list, experience level, and preferred modalities.",
            "Scan every CANDIDATES[] entry; decide include vs exclude using titles and typical Trailhead patterns.",
            "Order included units: prerequisites and conceptual intro before advanced units unless INTENT overrides.",
            "When INTENT favors hands-on engineering, prefer labs, projects, and code-heavy units; "
            "deprioritize quiz-only, exam prep, or trivia unless INTENT asks for them.",
            "For each ordered_units row: copy href and title exactly from the matching candidate; "
            "write reason as 8–25 words tying the unit to INTENT and its position in the queue.",
            "List excluded candidates with href (when applicable) and a concise exclusion reason.",
        ],
        "hard_rules": [
            "Every ordered_units[].href must match some candidates[].href exactly (same string).",
            "Never invent or merge URLs, query strings, or hosts outside the given hrefs.",
            "Do not output markdown, code fences, or prose outside the JSON object.",
        ],
    }


DEFAULT_SYSTEM_PROMPT = """You are a senior learning-path planner for Salesforce Trailhead.

## Inputs (in the user message JSON)
- **intent**: Natural-language goals: topics, depth, time, exclusions, and format preferences.
- **candidates**: The only units you may recommend. Each has **title** and **href** (Trailhead learn URLs).
- **execution_steps**, **hard_rules**, **meta**: Operational checklist — follow them.
- **planner_notes** (optional): Short notes from an earlier pass. Treat as hints, not overrides; INTENT still wins.

## Your objective
Build an **ordered study queue**: which units to open, in what order, and why — so a human can execute the plan without guessing.

## Reasoning policy
1. **Interpret intent literally** — including negatives ("no quizzes", "only Apex", "fast overview").
2. **Use titles as signals** — Trailhead titles usually reflect content type (intro, hands-on project, quiz, certification).
3. **Ordering** — Default: foundational → practice → advanced. If intent says "deep dive on X", cluster X-related units early.
4. **Assessments** — When intent is skills/coding/building, treat standalone quizzes and exam-prep-style units as low priority or **excluded**.
5. **Coverage** — Include every candidate that clearly fits; exclude misfits explicitly in **excluded** when you omit them from **ordered_units**.

## Output contract (strict)
- Respond with **JSON only** — no markdown, no code fences, no commentary.
- Root keys **must be exactly**: `"ordered_units"` and `"excluded"` (both arrays; either may be empty).
- Each **ordered_units** element: `"href"`, `"title"`, `"reason"`.
  - **href** / **title**: copied exactly from the matching **candidates** entry.
  - **reason**: non-empty; 8–25 words; state how the unit serves INTENT and why it ranks where it does.
- Each **excluded** element: `"href"` when you are excluding a known candidate; `"reason"` one short sentence.

## Shape (illustrative)
{"ordered_units":[{"href":"https://...","title":"...","reason":"..."}],"excluded":[{"href":"https://...","reason":"..."}]}
"""

REPAIR_SYSTEM_PROMPT = """You fix invalid ranking output for Trailhead unit selection.

The user JSON includes **intent**, **candidates**, **repair.invalid_output** (prior model text), **repair.validation_errors**, plus the same **execution_steps** and **hard_rules** as the primary task.

## What you must do
1. Diagnose why the prior output failed (bad JSON shape, wrong keys, invented hrefs, empty ordered_units when matches exist).
2. Produce **one** valid JSON object: keys **only** `ordered_units` and `excluded`, same semantics as the main ranker.
3. Every **ordered_units[].href** must be **copied character-for-character** from **candidates[].href**.
4. Preserve **title** from the matching candidate for each href.
5. Fill **reason** on every ordered row (8–25 words, actionable, tied to **intent**).
6. No markdown, no code fences, no text before or after the JSON.

If the prior output invented URLs, discard those rows and rebuild only from **candidates**.
"""

PLANNER_SYSTEM_PROMPT = """You are a planning analyst for a Trailhead study session. You do **not** rank units yet.

## Input
- **intent**: Learner goals.
- **units_preview**: First chunk of candidate units (title + href).
- **preview_count** / **total_candidates**: How many units were shown vs total (preview may be partial).
- **planning_task**: What to produce.

## Output (JSON only)
Keys **exactly**: `focus`, `constraints`, `ranking_hints` — no other top-level keys, no ordered_units.

- **focus** (one sentence): The single clearest learning outcome or theme to optimize for.
- **constraints** (one sentence): Hard boundaries from intent — time, exclusions, format, or level.
- **ranking_hints** (2–5 short lines, newline-separated or single string with semicolons): Concrete ordering ideas, e.g. "Intro before SOQL", "Skip quiz-only if intent is hands-on", "Group DML near SOQL".

Do not paste long URLs; refer to unit themes by title when needed. No markdown."""


def _system_prompt() -> str:
    path = os.environ.get("TRAILHEAD_AGENT_PROMPT_FILE", "").strip()
    if path:
        try:
            return Path(path).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            raise LLMProviderError(f"Cannot read TRAILHEAD_AGENT_PROMPT_FILE: {e}") from e
    return DEFAULT_SYSTEM_PROMPT


def _ranking_repair_enabled() -> bool:
    return os.environ.get("LLM_RANKING_REPAIR", "1").strip().lower() not in ("0", "false", "no", "off")


def _planner_phase_enabled() -> bool:
    return os.environ.get("LLM_PLANNER_PHASE", "0").strip().lower() in ("1", "true", "yes", "on")


def _openai_strict_schema_enabled() -> bool:
    return os.environ.get("LLM_OPENAI_STRICT_SCHEMA", "0").strip().lower() in ("1", "true", "yes", "on")


def _strip_fenced_json(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_llm_payload(raw: str) -> tuple[dict[str, Any], str]:
    stripped = _strip_fenced_json(raw)
    try:
        out = json.loads(stripped)
    except json.JSONDecodeError as e:
        raise LLMProviderError(f"LLM returned invalid JSON: {e}") from e
    if not isinstance(out, dict):
        raise LLMProviderError("LLM JSON root must be an object.")
    return out, stripped


def _retry_decorator() -> Callable[[Callable[..., T]], Callable[..., T]]:
    s = llm_retry_settings()
    return retry(
        stop=stop_after_attempt(s.max_attempts),
        wait=wait_exponential(multiplier=1, min=s.min_wait_s, max=s.max_wait_s),
        retry=retry_if_exception(_should_retry_llm_call),
        reraise=True,
    )


def _should_retry_llm_call(exc: BaseException) -> bool:
    if isinstance(exc, (LLMProviderError, json.JSONDecodeError)):
        return False
    if type(exc).__name__ in ("KeyboardInterrupt", "SystemExit"):
        return False
    try:
        from openai import APIConnectionError, APITimeoutError, RateLimitError

        if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
            return True
    except ImportError:
        pass
    try:
        from openai import InternalServerError
    except ImportError:
        pass
    else:
        if isinstance(exc, InternalServerError):
            return True
    try:
        import anthropic  # type: ignore[import-not-found]

        if isinstance(exc, anthropic.RateLimitError):
            return True
        if isinstance(exc, anthropic.APIStatusError):
            code = getattr(exc, "status_code", None)
            return code is not None and int(code) >= 500
    except ImportError:
        pass
    name = type(exc).__name__
    if name in (
        "ServiceUnavailable",
        "TooManyRequests",
        "InternalServerError",
        "GatewayTimeout",
        "DeadlineExceeded",
    ):
        return True
    msg = str(exc).lower()
    if "429" in msg or "503" in msg or "resource exhausted" in msg or "timeout" in msg:
        return True
    return False


@_retry_decorator()
def _openai_complete_json_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    from openai import OpenAI

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise LLMProviderError("Set OPENAI_API_KEY in your environment or .env file.")

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
    timeout = float(os.environ.get("LLM_HTTP_TIMEOUT_S", "120"))
    client = OpenAI(api_key=key, timeout=timeout)
    user_text = json.dumps(user_payload, ensure_ascii=False)
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
    }
    if _openai_strict_schema_enabled():
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "trailhead_ranking",
                "strict": True,
                "schema": openai_ranking_json_schema(),
            },
        }
    else:
        kwargs["response_format"] = {"type": "json_object"}
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        raise_mapped_llm_error("OpenAI", e)
    raw = (resp.choices[0].message.content or "").strip() or "{}"
    return _parse_llm_payload(raw)


@_retry_decorator()
def _anthropic_complete_json_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        import anthropic
    except ModuleNotFoundError as e:
        raise LLMProviderError(
            "LLM_PROVIDER=anthropic requires the anthropic package. "
            "Install: pip install 'trailhead-agent[anthropic]'"
        ) from e

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise LLMProviderError("Set ANTHROPIC_API_KEY in your environment or .env file.")

    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
    timeout = float(os.environ.get("LLM_HTTP_TIMEOUT_S", "120"))
    try:
        client = anthropic.Anthropic(api_key=key, timeout=timeout)
    except TypeError:
        client = anthropic.Anthropic(api_key=key)
    user_text = json.dumps(user_payload, ensure_ascii=False)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception as e:
        raise_mapped_llm_error("Anthropic", e)
    text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            text += block.text
    raw = text.strip() or "{}"
    return _parse_llm_payload(raw)


@_retry_decorator()
def _gemini_complete_json_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    key = (
        os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    if not key:
        raise LLMProviderError(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY in your environment or .env file."
        )

    model_id = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
    user_text = json.dumps(user_payload, ensure_ascii=False)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning(
            "google-genai not installed; falling back to deprecated google.generativeai. "
            "Install: pip install 'trailhead-agent[gemini]'"
        )
    else:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_id,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            raw = (response.text or "").strip() or "{}"
            return _parse_llm_payload(raw)
        except LLMProviderError:
            raise
        except Exception as e:
            raise_mapped_llm_error("Gemini", e)

    try:
        import google.generativeai as genai_legacy  # type: ignore[import-untyped]
    except ModuleNotFoundError as e:
        raise LLMProviderError(
            "Install Gemini support: pip install 'trailhead-agent[gemini]' (uses google-genai)."
        ) from e

    genai_legacy.configure(api_key=key)
    model = genai_legacy.GenerativeModel(model_id, system_instruction=system)
    try:
        resp = model.generate_content(
            user_text,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )
    except Exception as e:
        raise_mapped_llm_error("Gemini (legacy)", e)
    raw = (resp.text or "").strip() or "{}"
    return _parse_llm_payload(raw)


def _complete_json_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    if provider in ("anthropic", "claude"):
        return _anthropic_complete_json_raw(system, user_payload)
    if provider in ("gemini", "google"):
        return _gemini_complete_json_raw(system, user_payload)
    return _openai_complete_json_raw(system, user_payload)


def _openai_planner_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Planner uses json_object (not strict ranking schema)."""
    from openai import OpenAI

    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise LLMProviderError("Set OPENAI_API_KEY in your environment or .env file.")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip()
    timeout = float(os.environ.get("LLM_HTTP_TIMEOUT_S", "120"))
    client = OpenAI(api_key=key, timeout=timeout)
    user_text = json.dumps(user_payload, ensure_ascii=False)
    try:
        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text},
            ],
            temperature=0.3,
            max_tokens=512,
        )
    except Exception as e:
        raise_mapped_llm_error("OpenAI", e)
    raw = (resp.choices[0].message.content or "").strip() or "{}"
    return _parse_llm_payload(raw)


def _anthropic_planner_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        import anthropic
    except ModuleNotFoundError as e:
        raise LLMProviderError(
            "LLM_PROVIDER=anthropic requires the anthropic package. "
            "Install: pip install 'trailhead-agent[anthropic]'"
        ) from e
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise LLMProviderError("Set ANTHROPIC_API_KEY in your environment or .env file.")
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514").strip()
    timeout = float(os.environ.get("LLM_HTTP_TIMEOUT_S", "120"))
    try:
        client = anthropic.Anthropic(api_key=key, timeout=timeout)
    except TypeError:
        client = anthropic.Anthropic(api_key=key)
    user_text = json.dumps(user_payload, ensure_ascii=False)
    try:
        msg = client.messages.create(
            model=model,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_text}],
        )
    except Exception as e:
        raise_mapped_llm_error("Anthropic", e)
    text = ""
    for block in msg.content:
        if hasattr(block, "text"):
            text += block.text
    raw = text.strip() or "{}"
    return _parse_llm_payload(raw)


def _gemini_planner_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    key = (
        os.environ.get("GOOGLE_API_KEY", "").strip()
        or os.environ.get("GEMINI_API_KEY", "").strip()
    )
    if not key:
        raise LLMProviderError(
            "Set GOOGLE_API_KEY or GEMINI_API_KEY in your environment or .env file."
        )
    model_id = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash").strip()
    user_text = json.dumps(user_payload, ensure_ascii=False)
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        pass
    else:
        try:
            client = genai.Client(api_key=key)
            response = client.models.generate_content(
                model=model_id,
                contents=user_text,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    response_mime_type="application/json",
                    temperature=0.3,
                    max_output_tokens=512,
                ),
            )
            raw = (response.text or "").strip() or "{}"
            return _parse_llm_payload(raw)
        except LLMProviderError:
            raise
        except Exception as e:
            raise_mapped_llm_error("Gemini", e)
    try:
        import google.generativeai as genai_legacy  # type: ignore[import-untyped]
    except ModuleNotFoundError as e:
        raise LLMProviderError(
            "Install Gemini support: pip install 'trailhead-agent[gemini]' (uses google-genai)."
        ) from e
    genai_legacy.configure(api_key=key)
    model = genai_legacy.GenerativeModel(model_id, system_instruction=system)
    try:
        resp = model.generate_content(
            user_text,
            generation_config={
                "temperature": 0.3,
                "response_mime_type": "application/json",
                "max_output_tokens": 512,
            },
        )
    except Exception as e:
        raise_mapped_llm_error("Gemini (legacy)", e)
    raw = (resp.text or "").strip() or "{}"
    return _parse_llm_payload(raw)


def _planner_complete_json_raw(system: str, user_payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
    provider = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    if provider in ("anthropic", "claude"):
        return _anthropic_planner_raw(system, user_payload)
    if provider in ("gemini", "google"):
        return _gemini_planner_raw(system, user_payload)
    return _openai_planner_raw(system, user_payload)


def _run_planner_notes(intent: str, candidates: list[UnitRef]) -> str:
    logger.info("pipeline_stage=planner")
    preview = [{"title": u.title, "href": u.href} for u in candidates[:24]]
    payload: dict[str, Any] = {
        "planning_task": {
            "produce": ["focus", "constraints", "ranking_hints"],
            "rules": [
                "Derive focus and constraints only from intent and unit titles in the preview.",
                "If preview_count < total_candidates, still write ranking_hints that generalize to unseen units.",
            ],
        },
        "intent": intent,
        "units_preview": preview,
        "preview_count": len(preview),
        "total_candidates": len(candidates),
    }
    try:
        data, _raw = _planner_complete_json_raw(PLANNER_SYSTEM_PROMPT, payload)
        brief = try_parse_planner_dict(data)
    except Exception as e:
        logger.warning("Planner phase failed (continuing without planner notes): %s", e)
        return ""
    parts = [brief.focus, brief.constraints, brief.ranking_hints]
    return "\n".join(p for p in parts if p).strip()


def _rank_once(
    system: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], str, LLMRankingResponse | None]:
    """Single LLM ranking attempt: raw JSON dict, stripped raw text, validated model or None."""
    data, raw_stripped = _complete_json_raw(system, payload)
    parsed, verr = try_parse_ranking_dict(data)
    if verr:
        logger.info("pipeline_stage=validate ranking_schema_error=%s", verr[:500])
        return data, raw_stripped, None
    return data, raw_stripped, parsed


def apply_llm_ranking(data: dict[str, Any], candidates: list[UnitRef]) -> list[UnitRef]:
    """Pure ranking from parsed LLM JSON (testable)."""
    parsed, _err = try_parse_ranking_dict(data)
    if parsed is None:
        return []
    return materialize_ordered_units(parsed, candidates)


def select_and_rank_units(*, intent: str, candidates: list[UnitRef]) -> list[UnitRef]:
    if not candidates:
        return []

    logger.info("pipeline_stage=orchestrator langgraph=1")
    try:
        return run_ranking_graph(intent=intent, candidates=candidates)
    except LLMProviderError:
        raise
    except Exception as e:
        raise LLMProviderError(f"LangGraph ranking failed: {e}") from e
