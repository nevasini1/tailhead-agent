from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass

from playwright.sync_api import Page

from trailhead_agent import __version__
from trailhead_agent.config import (
    AgentConfig,
    persistent_profile_dir,
    record_video_scroll_demo,
    trailhead_origin,
)
from trailhead_agent.context import get_trace_id
from trailhead_agent.discovery import collect_units_for_seed
from trailhead_agent.llm_agent import select_and_rank_units
from trailhead_agent.models import UnitRef
from trailhead_agent.session import TrailheadBrowser
from trailhead_agent.validation import validate_start_url

logger = logging.getLogger(__name__)


_MAX_WALK_RANKED = 100


def _page_settle_ms() -> int:
    try:
        return max(500, int(os.environ.get("TRAILHEAD_PAGE_SETTLE_MS", "3500")))
    except ValueError:
        return 3500


def _clamp_walk_count(n: int) -> int:
    return max(0, min(int(n), _MAX_WALK_RANKED))


@dataclass
class RunPlan:
    label: str
    start_url: str
    intent: str
    units: list[UnitRef]
    trace_id: str | None = None
    duration_ms: int | None = None
    walk_ranked_visits: int | None = None

    def to_json_dict(self) -> dict:
        d: dict = {
            "agent_version": __version__,
            "label": self.label,
            "start_url": self.start_url,
            "intent": self.intent,
            "units": [
                {"title": u.title, "href": u.href, "reason": u.reason or ""} for u in self.units
            ],
        }
        if self.trace_id:
            d["trace_id"] = self.trace_id
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.walk_ranked_visits is not None:
            d["walk_ranked_visits"] = self.walk_ranked_visits
        return d


def _scroll_demo_for_recording(page: Page) -> None:
    """Smooth scroll so Playwright recordings show something moving (discovery itself has no clicks)."""
    if not record_video_scroll_demo():
        return
    try:
        page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
        page.wait_for_timeout(1500)
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        page.wait_for_timeout(1000)
    except Exception as e:
        logger.debug("Recording scroll demo skipped: %s", e)


def walk_ranked_units_for_recording(page: Page, units: list[UnitRef], *, max_visits: int) -> list[str]:
    """
    Visit the first max_visits ranked URLs in order (navigation only — no quiz automation).
    Intended for E2E recordings so the WebM shows clear progression after the LLM ranks.
    Returns hrefs successfully loaded, in visit order (skips failures).
    """
    n = _clamp_walk_count(max_visits)
    if n <= 0 or not units:
        return []
    to_visit = units[:n]
    settle = _page_settle_ms()
    visited: list[str] = []
    for i, u in enumerate(to_visit):
        logger.info(
            "e2e_walk_ranked step=%d/%d title=%r href=%s",
            i + 1,
            len(to_visit),
            u.title,
            u.href,
        )
        try:
            page.goto(u.href, wait_until="domcontentloaded")
            page.wait_for_timeout(settle)
            visited.append(u.href)
        except Exception as e:
            logger.warning("e2e_walk_ranked navigation failed for %s: %s", u.href, e)
            continue
        _scroll_demo_for_recording(page)
    return visited


def build_plan(cfg: AgentConfig, page: Page, *, start_url: str, label: str, intent: str) -> RunPlan:
    raw_units = collect_units_for_seed(page, start_url)
    _scroll_demo_for_recording(page)
    ranked = select_and_rank_units(intent=intent, candidates=raw_units)
    return RunPlan(label=label, start_url=start_url, intent=intent, units=ranked)


def try_login(page: Page, selectors: dict[str, str]) -> bool:
    email = os.environ.get("TRAILHEAD_EMAIL", "").strip()
    password = os.environ.get("TRAILHEAD_PASSWORD", "").strip()
    if not email or not password:
        logger.warning("TRAILHEAD_EMAIL / TRAILHEAD_PASSWORD not set; skipping password login.")
        return False
    try:
        page.goto(trailhead_origin(), wait_until="domcontentloaded")
        for sel in (
            'a[href*="login"]',
            'button:has-text("Log In")',
            'a:has-text("Log In")',
        ):
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click()
                page.wait_for_timeout(500)
                break
        page.fill(selectors.get("login_email_input", 'input[type="email"]'), email)
        page.fill(selectors.get("login_password_input", 'input[type="password"]'), password)
        page.click(selectors.get("login_submit", 'button[type="submit"]'))
        page.wait_for_load_state("domcontentloaded", timeout=45000)
        page.wait_for_timeout(1500)
        return True
    except Exception as e:
        logger.warning("Login attempt failed: %s", e)
        return False


def run_auth_setup(cfg: AgentConfig) -> None:
    if persistent_profile_dir() is None:
        logger.error(
            "Set TRAILHEAD_BROWSER_USER_DATA_DIR in .env to a dedicated folder "
            r"(e.g. C:\Users\YOU\trailhead-chromium-profile). Required for Google SSO."
        )
        return
    print(
        "Opening Trailhead in Chromium. Sign in with Google (or your method). "
        "When your avatar/name shows you are logged in, return here and press Enter."
    )
    with TrailheadBrowser(cfg, force_visible=True) as br:
        br.page.goto(trailhead_origin(), wait_until="domcontentloaded")
        input()
    logger.info("Session data saved under %s", persistent_profile_dir())


def run_dry_plan(
    cfg: AgentConfig,
    *,
    start_url: str,
    intent: str,
    label: str | None = None,
    log_units: bool = True,
    walk_ranked: int = 0,
) -> RunPlan:
    """Discover units in the browser, then LLM agent filters and ranks (no YAML keyword lists)."""
    start_url = validate_start_url(start_url)
    walk_n = _clamp_walk_count(walk_ranked)
    t0 = time.monotonic()
    with TrailheadBrowser(cfg) as br:
        page = br.page
        try_login(page, cfg.selectors)
        br.delay()
        raw = collect_units_for_seed(page, start_url)
        _scroll_demo_for_recording(page)
        ranked = select_and_rank_units(intent=intent, candidates=raw)
        walk_visited: list[str] = []
        if walk_n > 0 and ranked:
            walk_visited = walk_ranked_units_for_recording(page, ranked, max_visits=walk_n)
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        plan = RunPlan(
            label=label or start_url,
            start_url=start_url,
            intent=intent,
            units=ranked,
            trace_id=get_trace_id(),
            duration_ms=elapsed_ms,
            walk_ranked_visits=(len(walk_visited) if walk_n > 0 else None),
        )
        logger.info(
            "Plan %r: %d units after LLM agent (%d raw links discovered) duration_ms=%d",
            plan.label,
            len(plan.units),
            len(raw),
            elapsed_ms,
        )
        if walk_n > 0:
            logger.info(
                "e2e_walk_ranked requested=%d visited_ok=%d",
                walk_n,
                len(walk_visited),
            )
        if log_units:
            for u in plan.units[:20]:
                logger.info("  - %s | %s", u.title, u.href)
            if len(plan.units) > 20:
                logger.info("  ... %d more", len(plan.units) - 20)
    return plan


def open_first_ranked_unit(
    cfg: AgentConfig,
    *,
    start_url: str,
    intent: str,
    label: str | None = None,
    visit_count: int = 1,
) -> tuple[bool, str | None, list[str], list[str]]:
    """
    Open the first ``visit_count`` LLM-ranked units in order (navigation only).
    Returns (success, first_opened_href_or_none, all_ranked_hrefs, visited_hrefs_in_order).
    """
    start_url = validate_start_url(start_url)
    vc = max(1, _clamp_walk_count(visit_count))
    with TrailheadBrowser(cfg) as br:
        page = br.page
        try_login(page, cfg.selectors)
        br.delay()
        plan = build_plan(cfg, page, start_url=start_url, label=label or start_url, intent=intent)
        ranked = [u.href for u in plan.units]
        if not plan.units:
            logger.error("No units after LLM selection for %s", plan.start_url)
            return False, None, ranked, []
        n = min(vc, len(plan.units))
        visited_hrefs = walk_ranked_units_for_recording(page, plan.units, max_visits=n)
        if not visited_hrefs:
            logger.error("open-unit: no successful navigations among top %d ranked units", n)
            return False, None, ranked, []
        return True, visited_hrefs[0], ranked, visited_hrefs
