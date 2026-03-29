"""
When TRAILHEAD_RECORD_VIDEO_DIR is set, persist machine-readable run output next to Playwright .webm files.
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from trailhead_agent.config import record_video_dir
from trailhead_agent.context import get_trace_id
from trailhead_agent.e2e_viewer import viewer_html_report_enabled, write_e2e_viewer_html

if TYPE_CHECKING:
    from trailhead_agent.runner import RunPlan

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "e2e-manifest.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def webm_basenames(root: Path | None) -> set[str]:
    if root is None or not root.is_dir():
        return set()
    return {p.name for p in root.glob("*.webm")}


def new_webm_names_sorted_by_mtime(root: Path, before: set[str]) -> list[str]:
    """Filenames of .webm files that appeared since ``before`` (sorted by mtime ascending)."""
    after = webm_basenames(root)
    new_names = sorted(after - before, key=lambda n: (root / n).stat().st_mtime)
    return new_names


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


def friendly_video_names_enabled() -> bool:
    """Rename Playwright hash .webm files to readable names (plan-primary.webm, org-prepare.webm, …)."""
    v = os.environ.get("TRAILHEAD_E2E_FRIENDLY_VIDEO_NAMES", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def _unlink_if_exists(path: Path) -> None:
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def _rename_webm_replace(src: Path, dest: Path) -> None:
    """Replace dest with src; retry briefly on Windows (browser/antivirus file locks)."""
    last_err: OSError | None = None
    for attempt in range(25):
        try:
            _unlink_if_exists(dest)
            src.rename(dest)
            return
        except OSError as e:
            last_err = e
            if getattr(e, "winerror", None) == 32 or e.errno == 13:
                time.sleep(0.12)
                continue
            raise
    if last_err:
        raise last_err


def friendly_rename_plan_session(root: Path, names: list[str]) -> tuple[list[str], str | None]:
    """``plan-primary.webm``, ``plan-session-01.webm``, …"""
    if not names:
        return [], None
    primary_old = choose_primary_webm(root, names) or names[0]
    rest = sorted(n for n in names if n != primary_old)
    ordered = [primary_old] + rest
    new_names: list[str] = []
    for i, old in enumerate(ordered):
        src = root / old
        if not src.is_file():
            continue
        dest_name = "plan-primary.webm" if i == 0 else f"plan-session-{i:02d}.webm"
        dest = root / dest_name
        _rename_webm_replace(src, dest)
        new_names.append(dest_name)
    new_primary = new_names[0] if new_names else None
    if new_names:
        logger.info("e2e_friendly_video_names kind=plan files=%s primary=%s", new_names, new_primary)
    return new_names, new_primary


def friendly_rename_open_unit_session(root: Path, names: list[str]) -> tuple[list[str], str | None]:
    """``open-unit-primary.webm``, ``open-unit-session-01.webm``, …"""
    if not names:
        return [], None
    primary_old = choose_primary_webm(root, names) or names[0]
    rest = sorted(n for n in names if n != primary_old)
    ordered = [primary_old] + rest
    new_names: list[str] = []
    for i, old in enumerate(ordered):
        src = root / old
        if not src.is_file():
            continue
        dest_name = "open-unit-primary.webm" if i == 0 else f"open-unit-session-{i:02d}.webm"
        dest = root / dest_name
        _rename_webm_replace(src, dest)
        new_names.append(dest_name)
    new_primary = new_names[0] if new_names else None
    if new_names:
        logger.info("e2e_friendly_video_names kind=open_unit files=%s primary=%s", new_names, new_primary)
    return new_names, new_primary


def friendly_rename_org_prepare_session(root: Path, names: list[str]) -> tuple[list[str], str | None]:
    """``org-prepare.webm``, ``org-prepare-session-01.webm``, …"""
    if not names:
        return [], None
    primary_old = choose_primary_webm(root, names) or names[0]
    rest = sorted(n for n in names if n != primary_old)
    ordered = [primary_old] + rest
    new_names: list[str] = []
    for i, old in enumerate(ordered):
        src = root / old
        if not src.is_file():
            continue
        dest_name = "org-prepare.webm" if i == 0 else f"org-prepare-session-{i:02d}.webm"
        dest = root / dest_name
        _rename_webm_replace(src, dest)
        new_names.append(dest_name)
    new_primary = new_names[0] if new_names else None
    if new_names:
        logger.info("e2e_friendly_video_names kind=org_prepare files=%s primary=%s", new_names, new_primary)
    return new_names, new_primary


def choose_primary_webm(root: Path, names: list[str]) -> str | None:
    """Prefer the largest new .webm (main session) over short sidecars from closed profile tabs."""
    best: str | None = None
    best_size = -1
    for name in names:
        p = root / name
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_size > best_size:
            best_size = st.st_size
            best = name
    return best


def metadata_for_webm_names(
    root: Path,
    names: list[str],
    *,
    primary_name: str | None,
) -> list[dict[str, Any]]:
    """Per-file rows for this Playwright session (role primary vs session)."""
    out: list[dict[str, Any]] = []
    for name in names:
        p = root / name
        try:
            st = p.stat()
        except OSError:
            continue
        out.append(
            {
                "name": name,
                "role": "primary" if primary_name and name == primary_name else "session",
                "size_bytes": st.st_size,
                "mtime_utc": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return out


def other_webms_in_dir(root: Path, session_names: set[str], *, limit: int = 15) -> list[dict[str, Any]]:
    """Other .webm files in the directory not attributed to this session (older runs, manual drops)."""
    extra: list[dict[str, Any]] = []
    for row in _snapshot_webms(root):
        if row["name"] in session_names:
            continue
        extra.append(row)
        if len(extra) >= limit:
            break
    return extra


def append_e2e_manifest_recording(root: Path, entry: dict[str, Any]) -> None:
    """
    Append a clip description to e2e-manifest.json (plan, open-unit, org prepare, etc.).
    """
    path = root / MANIFEST_FILENAME
    doc: dict[str, Any]
    if path.is_file():
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            doc = {"version": 1, "recordings": []}
    else:
        doc = {"version": 1, "recordings": []}
    recs = doc.get("recordings")
    if not isinstance(recs, list):
        recs = []
    entry = {**entry, "saved_at_utc": entry.get("saved_at_utc") or _utc_now_iso()}
    recs.append(entry)
    doc["recordings"] = recs
    doc["video_dir"] = str(root)
    doc["updated_at_utc"] = _utc_now_iso()
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("e2e_manifest_updated path=%s recordings=%d", path, len(recs))


def write_e2e_plan_output(plan: RunPlan) -> Path | None:
    """
    Write plan JSON beside recorded videos: e2e-plan-<trace_id>.json and e2e-plan-latest.json.
    ``video_files`` lists only clips from this command's browser session (see ``role`` / ``primary_video``).
    """
    root = record_video_dir()
    if root is None:
        return None
    tid = (plan.trace_id or get_trace_id() or "unknown").replace("/", "_")
    session_names = list(plan.e2e_session_videos or [])
    primary = plan.primary_video
    session_meta = metadata_for_webm_names(root, session_names, primary_name=primary)
    session_set = set(session_names)
    body: dict[str, Any] = {
        "saved_at_utc": _utc_now_iso(),
        "command": "plan",
        "video_dir": str(root),
        "video_files": session_meta,
        "video_files_other_in_dir": other_webms_in_dir(root, session_set),
        **plan.to_json_dict(),
    }
    path = root / f"e2e-plan-{tid}.json"
    text = json.dumps(body, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    (root / "e2e-plan-latest.json").write_text(text, encoding="utf-8")
    append_e2e_manifest_recording(
        root,
        {
            "source": "plan",
            "command": "plan",
            "trace_id": plan.trace_id,
            "primary_video": plan.primary_video,
            "new_videos": list(plan.e2e_session_videos or []),
            "start_url": plan.start_url,
        },
    )
    logger.info("e2e_plan_output_written path=%s", path)
    if viewer_html_report_enabled():
        write_e2e_viewer_html(root)
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
    primary_video: str | None = None,
    e2e_session_videos: list[str] | None = None,
) -> Path | None:
    root = record_video_dir()
    if root is None:
        return None
    tid = (get_trace_id() or "unknown").replace("/", "_")
    session_names = list(e2e_session_videos or [])
    session_meta = metadata_for_webm_names(root, session_names, primary_name=primary_video)
    session_set = set(session_names)
    body: dict[str, Any] = {
        "saved_at_utc": _utc_now_iso(),
        "command": "open-unit",
        "success": success,
        "video_dir": str(root),
        "video_files": session_meta,
        "video_files_other_in_dir": other_webms_in_dir(root, session_set),
        "primary_video": primary_video,
        "e2e_session_videos": e2e_session_videos or [],
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
    append_e2e_manifest_recording(
        root,
        {
            "source": "open_unit",
            "command": "open-unit",
            "trace_id": get_trace_id(),
            "primary_video": primary_video,
            "new_videos": list(e2e_session_videos or []),
            "start_url": start_url,
        },
    )
    logger.info("e2e_open_unit_output_written path=%s", path)
    if viewer_html_report_enabled():
        write_e2e_viewer_html(root)
    return path
