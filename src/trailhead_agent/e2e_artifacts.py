"""
When TRAILHEAD_RECORD_VIDEO_DIR is set, persist machine-readable run output next to Playwright .webm files.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from trailhead_agent.config import record_video_dir
from trailhead_agent.context import get_trace_id

if TYPE_CHECKING:
    from trailhead_agent.runner import RunPlan

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _snapshot_webms(root: Path) -> list[dict[str, Any]]:
    """Most recent .webm files in the recording directory (for correlating output ↔ video)."""
    rows: list[tuple[int, dict[str, Any]]] = []
    for p in root.glob("*.webm"):
        try:
            st = p.stat()
        except OSError:
            continue
        mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
        rows.append(
            (
                mtime_ns,
                {
                    "name": p.name,
                    "size_bytes": st.st_size,
                    "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
                },
            )
        )
    rows.sort(key=lambda x: x[0], reverse=True)
    return [r[1] for r in rows[:20]]


def write_e2e_plan_output(plan: RunPlan) -> Path | None:
    """
    Write plan JSON beside recorded videos: e2e-plan-<trace_id>.json and e2e-plan-latest.json.
    """
    root = record_video_dir()
    if root is None:
        return None
    tid = (plan.trace_id or get_trace_id() or "unknown").replace("/", "_")
    body: dict[str, Any] = {
        "saved_at_utc": _utc_now_iso(),
        "command": "plan",
        "video_dir": str(root),
        "video_files": _snapshot_webms(root),
        **plan.to_json_dict(),
    }
    path = root / f"e2e-plan-{tid}.json"
    text = json.dumps(body, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    (root / "e2e-plan-latest.json").write_text(text, encoding="utf-8")
    logger.info("e2e_plan_output_written path=%s", path)
    return path


def write_e2e_open_unit_output(
    *,
    start_url: str,
    intent: str,
    label: str | None,
    success: bool,
    opened_href: str | None,
    ranked_unit_hrefs: list[str],
    visit_count: int | None = None,
    visited_unit_hrefs: list[str] | None = None,
) -> Path | None:
    root = record_video_dir()
    if root is None:
        return None
    tid = (get_trace_id() or "unknown").replace("/", "_")
    body: dict[str, Any] = {
        "saved_at_utc": _utc_now_iso(),
        "command": "open-unit",
        "success": success,
        "video_dir": str(root),
        "video_files": _snapshot_webms(root),
        "trace_id": get_trace_id(),
        "label": label or start_url,
        "start_url": start_url,
        "intent": intent,
        "opened_href": opened_href,
        "ranked_unit_hrefs": ranked_unit_hrefs,
    }
    if visit_count is not None:
        body["visit_count"] = visit_count
    if visited_unit_hrefs is not None:
        body["visited_unit_hrefs"] = visited_unit_hrefs
    path = root / f"e2e-open-unit-{tid}.json"
    text = json.dumps(body, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    (root / "e2e-open-unit-latest.json").write_text(text, encoding="utf-8")
    logger.info("e2e_open_unit_output_written path=%s", path)
    return path
