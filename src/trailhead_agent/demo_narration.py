"""
Human-readable **demo narration** on **stderr** so stdout stays clean for ``plan --json``.

Shows what was passed in (URLs, intent, flags), recording/browser prefs, discovery results,
and each LLM orchestration step. Disable with ``TRAILHEAD_DEMO_NARRATION=0``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

PREFIX = "trailhead-agent"


def demo_narration_enabled() -> bool:
    """Narration is **on** by default (stderr). Set ``TRAILHEAD_DEMO_NARRATION=0`` for quiet CI logs."""
    raw = os.environ.get("TRAILHEAD_DEMO_NARRATION", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    return True


def _emit(lines: list[str]) -> None:
    for line in lines:
        print(f"[{PREFIX}] {line}", file=sys.stderr, flush=True)


def narrate_plan_session(
    *,
    start_url: str,
    intent: str,
    label: str | None,
    walk_ranked: int,
    artifacts_dir_resolved: Path | None,
    json_stdout: bool,
    config_path: Path | None,
    trace_id: str,
) -> None:
    if not demo_narration_enabled():
        return
    prov = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    model = (
        os.environ.get("OPENAI_MODEL", "").strip()
        or os.environ.get("GEMINI_MODEL", "").strip()
        or os.environ.get("ANTHROPIC_MODEL", "").strip()
        or "(provider default)"
    )
    lines = [
        "",
        "──────── Plan run (what you asked for) ────────",
        f"trace_id: {trace_id}",
        f"start_url (--start-url or TRAILHEAD_START_URL): {start_url}",
        f"intent (--intent or TRAILHEAD_INTENT): {intent!r}",
    ]
    if label:
        lines.append(f"label (--label): {label!r}")
    lines.append(f"--walk-ranked: {walk_ranked} (after ranking, visit first N unit URLs in the browser when >0)")
    lines.append(f"LLM_PROVIDER: {prov}  ·  model env hint: {model}")
    lines.append(
        f"LLM_PLANNER_PHASE: {os.environ.get('LLM_PLANNER_PHASE', '0')!r} "
        f"(1 = extra planner notes before rank)  ·  "
        f"LLM_RANKING_REPAIR: {os.environ.get('LLM_RANKING_REPAIR', '1')!r}"
    )
    if config_path:
        lines.append(f"config (--config): {config_path}")
    else:
        lines.append("config: default config/default.yaml (or TRAILHEAD_AGENT_CONFIG)")
    if artifacts_dir_resolved is not None:
        lines.append(f"Recording: --artifacts-dir → {artifacts_dir_resolved}")
        lines.append(f"  TRAILHEAD_RECORD_VIDEO_DIR={artifacts_dir_resolved}")
        lines.append(
            f"  TRAILHEAD_RECORDING_DEMO_AUTO={os.environ.get('TRAILHEAD_RECORDING_DEMO_AUTO', '1')!r} "
            f"(headed + slow_mo defaults unless you override)"
        )
        lines.append(f"  TRAILHEAD_AGENT_HEADLESS={os.environ.get('TRAILHEAD_AGENT_HEADLESS', '(unset)')!r}")
        lines.append(f"  TRAILHEAD_DEMO_SLOW_MO_MS={os.environ.get('TRAILHEAD_DEMO_SLOW_MO_MS', '(unset)')!r}")
    else:
        lines.append("Recording: off (no --artifacts-dir / TRAILHEAD_RECORD_VIDEO_DIR)")
    if json_stdout:
        lines.append("Output: JSON on stdout (this narration is on stderr only).")
    lines.append("The LLM must follow INTENT when ordering units; reasons explain each choice.")
    lines.append("────────────────────────────────────────────────")
    lines.append("")
    _emit(lines)


def narrate_discovery_start(*, start_url: str) -> None:
    if not demo_narration_enabled():
        return
    _emit(
        [
            "",
            "── Discovery (Playwright) ──",
            f"Loading {start_url} and collecting /content/learn/… unit links from the DOM (scroll + pagination as configured).",
            "",
        ]
    )


def narrate_discovery_done(*, candidate_count: int, titles_sample: list[str]) -> None:
    if not demo_narration_enabled():
        return
    lines = [
        "",
        f"── Discovery (browser) — {candidate_count} candidate link(s) from Trailhead DOM ──",
    ]
    for i, t in enumerate(titles_sample[:20], 1):
        lines.append(f"  {i}. {t}")
    if candidate_count > len(titles_sample[:20]):
        lines.append(f"  … ({candidate_count} total)")
    lines.append("Next: LangGraph sends INTENT + candidates to the LLM for ranking.")
    lines.append("")
    _emit(lines)


def narrate_llm_ranking_start(*, intent: str, candidates: list[Any]) -> None:
    if not demo_narration_enabled():
        return
    n = len(candidates)
    lines = [
        "",
        "── LLM ranking (orchestrator = LangGraph) ──",
        f"INTENT the model must honor: {intent!r}",
        f"Candidates passed to the model: {n} unit(s) (href allowlist — it cannot invent URLs).",
        "Execution policy (summary): interpret intent literally; order foundational → practice → advanced;",
        "prefer hands-on units when intent asks; emit ordered_units + excluded as JSON.",
        "",
    ]
    _emit(lines)


def narrate_graph_step(step: str, detail: str) -> None:
    if not demo_narration_enabled():
        return
    _emit([f"  ▸ {step}: {detail}"])


def narrate_planner_skipped() -> None:
    if not demo_narration_enabled():
        return
    _emit(
        [
            "  ▸ planner: skipped (LLM_PLANNER_PHASE is not 1; set LLM_PLANNER_PHASE=1 for an extra planning pass)."
        ]
    )


def narrate_planner_no_notes() -> None:
    if not demo_narration_enabled():
        return
    _emit(
        [
            "  ▸ planner: LLM_PLANNER_PHASE=1 but planner returned empty notes; "
            "rank proceeds without planner_notes in the payload."
        ]
    )


def narrate_planner_done(*, notes_preview: str) -> None:
    if not demo_narration_enabled():
        return
    raw = notes_preview or ""
    lp = len(raw)
    prev = raw.strip().replace("\n", " ")[:240]
    suffix = "…" if lp > len(prev) else ""
    _emit([f"  ▸ planner: notes added to payload ({lp} chars). Preview: {prev!r}{suffix}"])


def narrate_rank_primary_done(*, ordered_count: int, needs_repair: bool) -> None:
    if not demo_narration_enabled():
        return
    _emit(
        [
            f"  ▸ rank_primary: model returned {ordered_count} allowlisted row(s) in ordered_units.",
            f"    needs_repair={needs_repair} (schema / allowlist check).",
        ]
    )


def narrate_rank_repair_start() -> None:
    if not demo_narration_enabled():
        return
    _emit(["  ▸ rank_repair: running a second LLM call with repair hints (LLM_RANKING_REPAIR enabled)."])


def narrate_llm_ranking_result(units: list[Any]) -> None:
    if not demo_narration_enabled():
        return
    lines: list[str] = ["", f"── Final ranked queue ({len(units)} unit(s)) ──"]
    for i, u in enumerate(units, 1):
        title = getattr(u, "title", str(u))
        href = getattr(u, "href", "")
        reason = (getattr(u, "reason", None) or "").strip()
        lines.append(f"  {i}. {title}")
        lines.append(f"     {href}")
        if reason:
            snippet = reason if len(reason) <= 160 else reason[:157] + "…"
            lines.append(f"     reason: {snippet}")
    lines.append("")
    _emit(lines)


def narrate_plan_epilogue(*, start_url: str, walk_n: int, walk_visited: int) -> None:
    if not demo_narration_enabled():
        return
    if walk_n > 0 and walk_visited:
        msg = f"Recording epilogue: staying on last visited unit ({walk_visited} visit(s))."
    else:
        msg = f"Recording epilogue: navigating back to module start_url for dwell + scroll: {start_url}"
    _emit(["", f"── {msg} ──", ""])


def narrate_open_unit_session(
    *,
    start_url: str,
    intent: str,
    visit_count: int,
    artifacts_dir_resolved: Path | None,
    trace_id: str,
) -> None:
    if not demo_narration_enabled():
        return
    lines = [
        "",
        "──────── open-unit run ────────",
        f"trace_id: {trace_id}",
        f"start_url: {start_url}",
        f"intent: {intent!r}",
        f"--visit-count: {visit_count}",
    ]
    if artifacts_dir_resolved:
        lines.append(f"artifacts: {artifacts_dir_resolved}")
    lines.append("Will build the same ranked plan, then open the first N ranked unit URLs.")
    lines.append("────────────────────────────────")
    lines.append("")
    _emit(lines)


def narrate_org_prepare_session(
    *,
    start_url: str,
    open_playground: bool,
    record_dir: str | None,
    trace_id: str,
) -> None:
    if not demo_narration_enabled():
        return
    lines = [
        "",
        "──────── org prepare ────────",
        f"trace_id: {trace_id}",
        f"--start-url: {start_url}",
        f"--open-playground: {open_playground}",
    ]
    if record_dir:
        lines.append(f"TRAILHEAD_RECORD_VIDEO_DIR: {record_dir}")
        lines.append(
            f"  TRAILHEAD_RECORDING_DEMO_AUTO={os.environ.get('TRAILHEAD_RECORDING_DEMO_AUTO', '1')!r} "
            f"(headed + slow_mo when recording)"
        )
    lines.append(
        "This command does not run plan/LLM ranking; it opens Trailhead for Playground prep (human-in-the-loop)."
    )
    lines.append("─────────────────────────────")
    lines.append("")
    _emit(lines)
