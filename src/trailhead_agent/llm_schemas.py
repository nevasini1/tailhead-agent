"""
Pydantic contracts for LLM JSON (structured outputs + validation/repair loops).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from trailhead_agent.models import UnitRef

logger = logging.getLogger(__name__)


class OrderedUnitRow(BaseModel):
    """One ranked unit from the model (href allowlisting happens in materialize)."""

    model_config = ConfigDict(extra="ignore")

    href: str = Field(
        ...,
        min_length=1,
        description="Exact href string copied from the user-provided candidates list (no edits).",
    )
    title: str = Field(
        default="",
        max_length=500,
        description="Unit title from the candidate with the same href.",
    )
    reason: str = Field(
        default="",
        max_length=500,
        description="8–25 words: why this unit is included and how it fits the learner intent / ordering.",
    )


class ExcludedRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    href: str = Field(default="", max_length=2000, description="Candidate href if known; else empty.")
    reason: str = Field(
        default="",
        max_length=500,
        description="Brief justification for exclusion or deprioritization.",
    )


class LLMRankingResponse(BaseModel):
    """Root JSON object returned by ranking LLM calls."""

    model_config = ConfigDict(extra="forbid")

    ordered_units: list[OrderedUnitRow] = Field(default_factory=list)
    excluded: list[ExcludedRow] = Field(default_factory=list)


class PlannerBrief(BaseModel):
    """Optional first-pass planner output (loose schema for provider variance)."""

    model_config = ConfigDict(extra="ignore")

    focus: str = Field(default="", max_length=800, description="One sentence: primary learning outcome.")
    constraints: str = Field(default="", max_length=800, description="One sentence: boundaries from intent.")
    ranking_hints: str = Field(
        default="",
        max_length=1200,
        description="2–5 short lines: how the ranker should order and filter units.",
    )


def parse_ranking_dict(data: dict[str, Any]) -> LLMRankingResponse:
    return LLMRankingResponse.model_validate(data)


def try_parse_ranking_dict(data: dict[str, Any]) -> tuple[LLMRankingResponse | None, str | None]:
    try:
        return parse_ranking_dict(data), None
    except ValidationError as e:
        return None, str(e)


def materialize_ordered_units(resp: LLMRankingResponse, candidates: list[UnitRef]) -> list[UnitRef]:
    """Keep model order; drop unknown hrefs and duplicates."""
    by_href = {u.href: u for u in candidates}
    ordered: list[UnitRef] = []
    seen: set[str] = set()
    for row in resp.ordered_units:
        href = row.href.strip()
        if not href or href not in by_href or href in seen:
            continue
        logger.debug("keep %s — %s", href, row.reason)
        base = by_href[href]
        ordered.append(
            UnitRef(title=base.title, href=href, reason=(row.reason or "")[:500]),
        )
        seen.add(href)
    return ordered


def needs_repair_after_materialize(resp: LLMRankingResponse, ordered: list[UnitRef], candidates: list[UnitRef]) -> bool:
    """Model proposed units but none matched the allowlist (likely invented hrefs)."""
    if ordered or not candidates:
        return False
    return bool(resp.ordered_units)


def openai_ranking_json_schema() -> dict[str, Any]:
    """Schema blob for OpenAI `response_format.type=json_schema` + strict."""
    return LLMRankingResponse.model_json_schema(mode="serialization")


def try_parse_planner_dict(data: dict[str, Any]) -> PlannerBrief:
    try:
        return PlannerBrief.model_validate(data)
    except ValidationError:
        return PlannerBrief()
