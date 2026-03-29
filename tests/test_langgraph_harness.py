"""LangGraph is the mandatory ranking orchestrator."""

import pytest

from trailhead_agent.llm_schemas import LLMRankingResponse
from trailhead_agent.models import UnitRef


@pytest.fixture
def fresh_ranking_graph():
    pytest.importorskip("langgraph")
    from trailhead_agent.ranking_graph import reset_compiled_ranking_graph

    reset_compiled_ranking_graph()
    yield
    reset_compiled_ranking_graph()


def test_langgraph_ranking_happy_path(fresh_ranking_graph, monkeypatch):
    import trailhead_agent.llm_agent as la

    href = "https://trailhead.salesforce.com/content/learn/modules/m/u1"
    unit = UnitRef(title="A", href=href)

    def fake_rank_once(system: str, payload: dict) -> tuple[dict, str, LLMRankingResponse]:
        d = {"ordered_units": [{"href": href, "title": "A", "reason": "x"}], "excluded": []}
        return d, "{}", LLMRankingResponse.model_validate(d)

    monkeypatch.setattr(la, "_rank_once", fake_rank_once)
    from trailhead_agent.ranking_graph import reset_compiled_ranking_graph

    reset_compiled_ranking_graph()
    out = la.select_and_rank_units(intent="developer hands-on", candidates=[unit])
    assert [u.href for u in out] == [href]
    assert out[0].reason == "x"


def test_langgraph_repair_branch(fresh_ranking_graph, monkeypatch):
    import trailhead_agent.llm_agent as la

    href = "https://trailhead.salesforce.com/content/learn/modules/m/u2"
    unit = UnitRef(title="B", href=href)
    calls: list[int] = []

    def fake_rank_once(system: str, payload: dict) -> tuple[dict, str, LLMRankingResponse | None]:
        calls.append(1)
        if len(calls) == 1:
            bad = {"ordered_units": "not-a-list", "excluded": []}
            return bad, "{}", None
        d = {"ordered_units": [{"href": href, "title": "B", "reason": "fixed"}], "excluded": []}
        return d, "{}", LLMRankingResponse.model_validate(d)

    monkeypatch.setattr(la, "_rank_once", fake_rank_once)
    from trailhead_agent.ranking_graph import reset_compiled_ranking_graph

    reset_compiled_ranking_graph()
    out = la.select_and_rank_units(intent="dev", candidates=[unit])
    assert [u.href for u in out] == [href]
    assert out[0].reason == "fixed"
    assert len(calls) == 2
