"""Staged ranking pipeline: Pydantic validation + optional repair LLM pass."""

from typing import Any

from trailhead_agent.llm_agent import apply_llm_ranking, select_and_rank_units
from trailhead_agent.models import UnitRef


def test_apply_llm_ranking_rejects_extra_root_keys():
    a = UnitRef(title="A", href="https://trailhead.salesforce.com/content/learn/modules/m/u1")
    data = {"ordered_units": [], "excluded": [], "unexpected_root_key": True}
    assert apply_llm_ranking(data, [a]) == []


def test_repair_pass_after_invalid_schema(monkeypatch):
    monkeypatch.setenv("LLM_RANKING_REPAIR", "1")
    monkeypatch.delenv("LLM_PLANNER_PHASE", raising=False)
    a = UnitRef(title="A", href="https://trailhead.salesforce.com/content/learn/modules/m/u1")
    b = UnitRef(title="B", href="https://trailhead.salesforce.com/content/learn/modules/m/u2")
    good = {
        "ordered_units": [{"href": b.href, "title": b.title, "reason": "x"}],
        "excluded": [],
    }
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake(system: str, payload: dict[str, Any]) -> tuple[dict[str, Any], str]:
        calls.append((system, payload))
        if len(calls) == 1:
            return ({"ordered_units": "nope"}, '{"ordered_units": "nope"}')
        return (good, "{}")

    monkeypatch.setattr("trailhead_agent.llm_agent._complete_json_raw", fake)
    out = select_and_rank_units(intent="hands-on developer", candidates=[a, b])
    assert [u.href for u in out] == [b.href]
    assert len(calls) == 2
    assert "repair" in calls[1][1]
