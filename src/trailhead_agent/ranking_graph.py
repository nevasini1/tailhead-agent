"""
LangGraph-orchestrated multi-step ranking: prepare → planner → rank → (repair) → finalize.

This is the only ranking orchestrator (required dependency).
"""

from __future__ import annotations

import logging
from typing import Any, Literal

from typing_extensions import Required, TypedDict

from trailhead_agent.llm_schemas import materialize_ordered_units, needs_repair_after_materialize
from trailhead_agent.models import UnitRef

logger = logging.getLogger(__name__)

_compiled_graph: Any = None


class RankingState(TypedDict, total=False):
    """Shared LangGraph state (module-level so get_type_hints resolves Required)."""

    intent: Required[str]
    candidates: Required[list[dict[str, str]]]
    payload: dict[str, Any]
    planner_notes: str
    raw_primary: str
    parsed_primary_dump: dict[str, Any] | None
    primary_ordered_hrefs: list[str]
    primary_ranked: list[dict[str, str]]
    needs_repair: bool
    repair_attempted: bool
    raw_repair: str
    parsed_repair_dump: dict[str, Any] | None
    repair_ordered_hrefs: list[str]
    repair_ranked: list[dict[str, str]]
    result_hrefs: list[str]
    result_units: list[dict[str, str]]


def _units_from_dicts(rows: list[dict[str, str]]) -> list[UnitRef]:
    return [UnitRef(title=str(r.get("title", "")), href=str(r["href"])) for r in rows]


def _build_graph() -> Any:
    from langgraph.graph import END, START, StateGraph

    def node_prepare(state: RankingState) -> dict[str, Any]:
        import trailhead_agent.llm_agent as la
        from trailhead_agent.demo_narration import narrate_graph_step

        logger.info("orchestrator_node=prepare")
        n = len(state["candidates"])
        narrate_graph_step(
            "prepare",
            f"Built LLM user JSON: intent + {n} candidate(s) + execution_steps / hard_rules "
            f"(ranking_user_message_context).",
        )
        return {
            "payload": {
                **la.ranking_user_message_context(candidate_count=n),
                "intent": state["intent"],
                "candidates": state["candidates"],
            },
            "repair_attempted": False,
        }

    def node_planner(state: RankingState) -> dict[str, Any]:
        import trailhead_agent.llm_agent as la
        from trailhead_agent.demo_narration import narrate_planner_done, narrate_planner_no_notes, narrate_planner_skipped

        if not la._planner_phase_enabled():
            narrate_planner_skipped()
            return {}
        logger.info("orchestrator_node=planner")
        units = _units_from_dicts(state["candidates"])
        notes = la._run_planner_notes(state["intent"], units)
        if not notes:
            narrate_planner_no_notes()
            return {}
        p = dict(state["payload"])
        p["planner_notes"] = notes
        narrate_planner_done(notes_preview=notes)
        return {"payload": p, "planner_notes": notes}

    def node_rank_primary(state: RankingState) -> dict[str, Any]:
        import trailhead_agent.llm_agent as la
        from trailhead_agent.demo_narration import narrate_graph_step, narrate_rank_primary_done

        logger.info("orchestrator_node=rank_primary")
        narrate_graph_step(
            "rank_primary",
            "Calling the ranking LLM (JSON: ordered_units + excluded; every href must match discovery allowlist).",
        )
        system = la._system_prompt()
        _data, raw, parsed = la._rank_once(system, state["payload"])
        units = _units_from_dicts(state["candidates"])
        ordered = materialize_ordered_units(parsed, units) if parsed is not None else []
        need = (parsed is None) or needs_repair_after_materialize(parsed, ordered, units)
        ranked_rows = [{"title": u.title, "href": u.href, "reason": u.reason} for u in ordered]
        narrate_rank_primary_done(ordered_count=len(ordered), needs_repair=need)
        return {
            "raw_primary": raw,
            "parsed_primary_dump": parsed.model_dump() if parsed is not None else None,
            "primary_ordered_hrefs": [u.href for u in ordered],
            "primary_ranked": ranked_rows,
            "needs_repair": need,
        }

    def route_after_primary(state: RankingState) -> Literal["rank_repair", "finalize"]:
        import trailhead_agent.llm_agent as la

        if (
            state.get("needs_repair")
            and la._ranking_repair_enabled()
            and not state.get("repair_attempted")
        ):
            return "rank_repair"
        return "finalize"

    def node_rank_repair(state: RankingState) -> dict[str, Any]:
        import trailhead_agent.llm_agent as la
        from trailhead_agent.demo_narration import narrate_rank_repair_start

        logger.info("orchestrator_node=rank_repair")
        narrate_rank_repair_start()
        n = len(state["candidates"])
        repair_payload: dict[str, Any] = {
            **la.ranking_user_message_context(candidate_count=n),
            "intent": state["intent"],
            "candidates": state["payload"]["candidates"],
            "repair": {
                "invalid_output": (state.get("raw_primary") or "")[:12000],
                "validation_errors": "schema mismatch or no allowlisted hrefs in ordered_units",
            },
        }
        if state.get("planner_notes"):
            repair_payload["planner_notes"] = state["planner_notes"]
        _d, raw2, parsed2 = la._rank_once(la.REPAIR_SYSTEM_PROMPT, repair_payload)
        units = _units_from_dicts(state["candidates"])
        ordered = materialize_ordered_units(parsed2, units) if parsed2 is not None else []
        if parsed2 is not None and not ordered and needs_repair_after_materialize(
            parsed2, ordered, units
        ):
            logger.warning("Repair pass still produced no allowlisted units.")
        elif parsed2 is None:
            logger.warning("Repair pass returned invalid JSON/schema; raw excerpt=%s", raw2[:200])
        repair_rows = [{"title": u.title, "href": u.href, "reason": u.reason} for u in ordered]
        return {
            "repair_attempted": True,
            "raw_repair": raw2,
            "parsed_repair_dump": parsed2.model_dump() if parsed2 is not None else None,
            "repair_ordered_hrefs": [u.href for u in ordered],
            "repair_ranked": repair_rows,
        }

    def node_finalize(state: RankingState) -> dict[str, Any]:
        from trailhead_agent.demo_narration import narrate_graph_step

        logger.info("orchestrator_node=finalize")
        units = _units_from_dicts(state["candidates"])
        by_href = {u.href: u for u in units}
        primary_hrefs = state.get("primary_ordered_hrefs") or []
        repair_hrefs = state.get("repair_ordered_hrefs") or []
        primary_ranked = state.get("primary_ranked") or []
        repair_ranked = state.get("repair_ranked") or []
        repair_done = state.get("repair_attempted", False)

        if repair_done and repair_hrefs:
            chosen_rows = repair_ranked
        elif primary_hrefs:
            chosen_rows = primary_ranked
        elif repair_done:
            chosen_rows = repair_ranked
        else:
            chosen_rows = primary_ranked

        if not chosen_rows:
            final_hrefs = [u.href for u in units]
            result_units = [{"title": u.title, "href": u.href, "reason": u.reason} for u in units]
        else:
            filtered = [r for r in chosen_rows if r.get("href") in by_href]
            if not filtered:
                final_hrefs = [u.href for u in units]
                result_units = [{"title": u.title, "href": u.href, "reason": u.reason} for u in units]
            else:
                result_units = []
                for r in filtered:
                    href = str(r["href"])
                    result_units.append(
                        {
                            "title": by_href[href].title,
                            "href": href,
                            "reason": (str(r.get("reason") or ""))[:500],
                        }
                    )
                final_hrefs = [row["href"] for row in result_units]

        narrate_graph_step("finalize", f"Emitting {len(result_units)} ranked row(s) for navigation / JSON output.")
        return {"result_hrefs": final_hrefs, "result_units": result_units}

    g: StateGraph = StateGraph(state_schema=RankingState)
    g.add_node("prepare", node_prepare)
    g.add_node("planner", node_planner)
    g.add_node("rank_primary", node_rank_primary)
    g.add_node("rank_repair", node_rank_repair)
    g.add_node("finalize", node_finalize)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "planner")
    g.add_edge("planner", "rank_primary")
    g.add_conditional_edges(
        "rank_primary",
        route_after_primary,
        {"rank_repair": "rank_repair", "finalize": "finalize"},
    )
    g.add_edge("rank_repair", "finalize")
    g.add_edge("finalize", END)
    return g


def get_compiled_ranking_graph() -> Any:
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph().compile()
    return _compiled_graph


def reset_compiled_ranking_graph() -> None:
    """Test hook: clear cached graph after patching llm_agent."""
    global _compiled_graph
    _compiled_graph = None


def run_ranking_graph(*, intent: str, candidates: list[UnitRef]) -> list[UnitRef]:
    """Execute the LangGraph ranking workflow; returns UnitRefs in ranked order."""
    if not candidates:
        return []
    app = get_compiled_ranking_graph()
    seed = [{"title": u.title, "href": u.href} for u in candidates]
    out = app.invoke({"intent": intent, "candidates": seed})
    result_rows = out.get("result_units") or []
    by_href = {u.href: u for u in candidates}
    if result_rows:
        ordered: list[UnitRef] = []
        for r in result_rows:
            href = str(r.get("href", ""))
            if href not in by_href:
                continue
            ordered.append(
                UnitRef(
                    title=str(r.get("title") or by_href[href].title),
                    href=href,
                    reason=str(r.get("reason") or "")[:500],
                )
            )
        if ordered:
            return ordered
    hrefs = out.get("result_hrefs") or []
    ordered = [by_href[h] for h in hrefs if h in by_href]
    if not ordered:
        logger.warning("LangGraph ranking empty; falling back to discovery order.")
        return list(candidates)
    return ordered
