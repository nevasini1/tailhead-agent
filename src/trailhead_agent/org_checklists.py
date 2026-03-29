"""
Static checklist registry: module slug / href → OrgStep list (YAML).

No LLM cost; safe for CI. Override path with TRAILHEAD_ORG_CHECKLISTS_FILE or cwd config/org_checklists.yaml.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from trailhead_agent.errors import ConfigurationError
from trailhead_agent.org_executor import OrgStep, TrailheadUnitContext

logger = logging.getLogger(__name__)

_MODULE_PATH_RE = re.compile(
    r"/content/learn/modules/([^/]+)(?:/([^/?#]+))?",
    re.IGNORECASE,
)


def default_org_checklists_path() -> Path:
    env = (os.environ.get("TRAILHEAD_ORG_CHECKLISTS_FILE") or "").strip()
    if env:
        return Path(env).expanduser()
    cwd = Path.cwd() / "config" / "org_checklists.yaml"
    if cwd.is_file():
        return cwd
    return Path(__file__).resolve().parents[2] / "config" / "org_checklists.yaml"


def module_slug_from_href(href: str) -> str | None:
    """Return module id (first segment under .../modules/) or None."""
    m = _MODULE_PATH_RE.search(href or "")
    if not m:
        return None
    return m.group(1).strip().lower() or None


def load_checklist_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or default_org_checklists_path()
    if not p.is_file():
        raise ConfigurationError(f"Org checklists file not found: {p}")
    text = p.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in org checklists {p}: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigurationError(f"Org checklists root must be a mapping: {p}")
    return raw


def _rows_to_steps(rows: list[dict[str, Any]]) -> list[OrgStep]:
    out: list[OrgStep] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        sid = str(row.get("step_id") or f"step_{i + 1}")
        desc = str(row.get("description") or "").strip()
        ver = str(row.get("verification") or "manual").strip()
        if desc:
            out.append(OrgStep(step_id=sid, description=desc, verification=ver))
    return out


def resolve_checklist_for_context(
    ctx: TrailheadUnitContext,
    *,
    registry_path: Path | None = None,
) -> tuple[list[OrgStep], str]:
    """
    Return (steps, source_key) where source_key is module slug, 'default', or 'empty'.
    """
    reg = load_checklist_registry(registry_path)
    by_mod = reg.get("checklists_by_module") or {}
    default_rows = reg.get("default_module_steps") or []
    if not isinstance(by_mod, dict):
        by_mod = {}
    if not isinstance(default_rows, list):
        default_rows = []

    slug = (ctx.module_hint or "").strip().lower() or None
    if not slug:
        slug = module_slug_from_href(ctx.href)

    if slug and slug in by_mod and isinstance(by_mod[slug], list):
        steps = _rows_to_steps(by_mod[slug])
        if steps:
            return steps, slug

    if default_rows:
        steps = _rows_to_steps(default_rows)
        if steps:
            return steps, "default"

    return [], "empty"


def checklist_markdown_table(steps: list[OrgStep]) -> str:
    lines = ["| Step ID | Description | Verification |", "|---------|-------------|--------------|"]
    for s in steps:
        desc = s.description.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {s.step_id} | {desc} | {s.verification} |")
    return "\n".join(lines)


def checklist_json_list(steps: list[OrgStep]) -> list[dict[str, str]]:
    return [
        {"step_id": s.step_id, "description": s.description, "verification": s.verification} for s in steps
    ]
