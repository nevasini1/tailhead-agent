"""
Salesforce org / Playground execution layer.

Defines OrgExecutor protocol, noop default, and factory (TRAILHEAD_ORG_EXECUTOR=noop|cli).
Concrete CLI implementation: cli_org_executor.CliOrgExecutor.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrailheadUnitContext:
    """What the planner knows about the current learning unit."""

    title: str
    href: str
    module_hint: str | None = None


@dataclass(frozen=True)
class OrgStep:
    """A single hands-on step (human- or machine-verified)."""

    step_id: str
    description: str
    verification: str  # e.g. "manual", "sf_deploy"


@dataclass(frozen=True)
class OrgStepResult:
    """Outcome of execute_step (observable; avoid logging secrets)."""

    ok: bool
    message: str = ""


@runtime_checkable
class OrgExecutor(Protocol):
    """Implementations perform or assist Salesforce-side work."""

    def ensure_playground_ready(
        self,
        ctx: TrailheadUnitContext,
        *,
        org_alias: str | None = None,
    ) -> bool:
        """Return True if a usable org context exists (e.g. sf org display shows connected)."""

    def propose_steps(self, ctx: TrailheadUnitContext) -> list[OrgStep]:
        """Map unit href to a checklist (static YAML, docs, or future LLM draft)."""

    def execute_step(self, ctx: TrailheadUnitContext, step: OrgStep) -> OrgStepResult:
        """Run one step; return structured result (CLI deploy, or manual acknowledgment)."""


class NoopOrgExecutor:
    """Default stub: documents the extension point for reviewers."""

    def ensure_playground_ready(
        self,
        ctx: TrailheadUnitContext,
        *,
        org_alias: str | None = None,
    ) -> bool:
        _ = ctx, org_alias
        return False

    def propose_steps(self, ctx: TrailheadUnitContext) -> list[OrgStep]:
        _ = ctx
        return []

    def execute_step(self, ctx: TrailheadUnitContext, step: OrgStep) -> OrgStepResult:
        _ = ctx, step
        return OrgStepResult(ok=False, message="noop executor")


def get_default_org_executor() -> OrgExecutor:
    kind = os.environ.get("TRAILHEAD_ORG_EXECUTOR", "noop").strip().lower()
    if kind in ("cli", "sf"):
        from trailhead_agent.cli_org_executor import CliOrgExecutor

        return CliOrgExecutor()
    if kind not in ("noop", "none", ""):
        logger.warning("Unknown TRAILHEAD_ORG_EXECUTOR=%r; using noop", kind)
    return NoopOrgExecutor()
