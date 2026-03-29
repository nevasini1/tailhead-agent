"""
Salesforce CLI-backed OrgExecutor: org display, optional metadata deploy.

Subprocess calls use argv lists only; org alias is validated before interpolation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

from trailhead_agent.org_checklists import resolve_checklist_for_context
from trailhead_agent.org_executor import OrgStep, OrgStepResult, TrailheadUnitContext

logger = logging.getLogger(__name__)

_ALIAS_SAFE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def sf_on_path() -> bool:
    return shutil.which("sf") is not None


def sanitize_org_alias(raw: str | None) -> str | None:
    if not raw:
        return None
    s = raw.strip()
    if not s or not _ALIAS_SAFE.match(s):
        logger.warning("Ignoring unsafe or empty org alias value")
        return None
    return s


def resolve_org_alias(explicit: str | None) -> str | None:
    return sanitize_org_alias(explicit) or sanitize_org_alias(os.environ.get("TRAILHEAD_SF_ORG_ALIAS"))


def run_sf_org_display_json(
    *,
    org_alias: str | None,
    timeout_s: float = 60.0,
) -> tuple[int, dict[str, object] | None, str]:
    """Run `sf org display --json`; returns (code, parsed dict or None, stderr snippet)."""
    cmd = ["sf", "org", "display", "--json"]
    if org_alias:
        cmd.extend(["--target-org", org_alias])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, None, str(e)[:500]
    err = (proc.stderr or "")[:2000]
    if proc.returncode != 0:
        return proc.returncode, None, err
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return 1, None, err or "invalid JSON from sf"
    if not isinstance(data, dict):
        return 1, None, err
    return 0, data, err


def org_display_says_connected(data: dict[str, object]) -> bool:
    """Best-effort parse of `sf org display --json` (shape varies by CLI version)."""
    status = data.get("status")
    if status is not None and status != 0:
        return False
    result = data.get("result")
    if isinstance(result, dict):
        if result.get("connected") is True:
            return True
        if result.get("username"):
            return True
        cs = str(result.get("connectedStatus") or "").lower()
        if cs == "connected":
            return True
        for k in ("defaultMarker", "isDefaultUsername"):
            if result.get(k):
                return True
    return False


class CliOrgExecutor:
    """OrgExecutor using `sf` for org checks; checklists from YAML; deploy opt-in per step."""

    def __init__(
        self,
        *,
        org_alias: str | None = None,
        project_dir: Path | str | None = None,
        checklist_config: Path | None = None,
    ) -> None:
        self._org_alias = resolve_org_alias(org_alias)
        self._project_dir = Path(project_dir).expanduser() if project_dir else None
        self._checklist_path = checklist_config

    def ensure_playground_ready(
        self,
        ctx: TrailheadUnitContext,
        *,
        org_alias: str | None = None,
    ) -> bool:
        _ = ctx
        if not sf_on_path():
            logger.info("org_executor stage=ensure_playground_ready sf_on_path=false")
            return False
        alias = resolve_org_alias(org_alias) or self._org_alias
        code, data, err = run_sf_org_display_json(org_alias=alias)
        ok = code == 0 and data is not None and org_display_says_connected(data)
        logger.info(
            "org_executor stage=ensure_playground_ready ok=%s alias=%s sf_exit=%s",
            ok,
            alias or "(default)",
            code,
        )
        if err and not ok:
            logger.debug("sf stderr: %s", err[:500])
        return ok

    def propose_steps(self, ctx: TrailheadUnitContext) -> list[OrgStep]:
        steps, key = resolve_checklist_for_context(ctx, registry_path=self._checklist_path)
        logger.info("org_executor stage=propose_steps checklist_key=%s count=%d", key, len(steps))
        return steps

    def execute_step(self, ctx: TrailheadUnitContext, step: OrgStep) -> OrgStepResult:
        _ = ctx
        ver = (step.verification or "manual").strip().lower()
        if ver == "manual":
            return OrgStepResult(ok=True, message="Manual step — complete in your org and Trailhead.")

        if ver == "sf_deploy":
            if not sf_on_path():
                return OrgStepResult(ok=False, message="sf CLI not found on PATH")
            root = self._project_dir
            if root is None:
                env_dir = (os.environ.get("TRAILHEAD_ORG_PROJECT_DIR") or "").strip()
                root = Path(env_dir).expanduser() if env_dir else None
            if root is None or not root.is_dir():
                return OrgStepResult(
                    ok=False,
                    message=(
                        "sf_deploy requires --project-dir or TRAILHEAD_ORG_PROJECT_DIR "
                        "pointing to an SFDX project."
                    ),
                )
            alias = self._org_alias
            cmd = ["sf", "project", "deploy", "start", "--json"]
            if alias:
                cmd.extend(["--target-org", alias])
            logger.info("org_executor stage=execute_step sf_deploy cwd=%s", root)
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=600,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                return OrgStepResult(ok=False, message=str(e)[:500])
            snippet = ((proc.stdout or "") + (proc.stderr or ""))[-1500:]
            if proc.returncode != 0:
                return OrgStepResult(ok=False, message=f"deploy failed (exit {proc.returncode}): {snippet}")
            return OrgStepResult(ok=True, message="Deploy finished.")

        return OrgStepResult(ok=False, message=f"Unsupported verification type: {step.verification}")
