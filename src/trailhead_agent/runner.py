from __future__ import annotations

import logging
import os
import random
import re
import time
from dataclasses import dataclass

from playwright.sync_api import Page

from trailhead_agent import __version__
from trailhead_agent.config import (
    AgentConfig,
    persistent_profile_dir,
    record_video_dir,
    record_video_scroll_demo,
    trailhead_origin,
)
from trailhead_agent.context import get_trace_id
from trailhead_agent.demo_narration import narrate_discovery_done, narrate_discovery_start, narrate_plan_epilogue
from trailhead_agent.demo_titlecards import (
    demo_after_discovery,
    demo_after_llm_rank,
    demo_before_walk_unit,
    demo_llm_ranking_output_slide,
    demo_plan_what_you_asked,
    demo_recording_end_card,
    inject_recording_corner_tag,
)
from trailhead_agent.browser_agent_primitives import (
    recording_humanish_scroll_down,
    recording_scroll_toward_top,
    trailhead_shell_wait_timeout_ms,
    wait_for_trailhead_shell_ready,
)
from trailhead_agent.discovery import collect_units_for_seed
from trailhead_agent.e2e_artifacts import (
    choose_primary_webm,
    friendly_rename_open_unit_session,
    friendly_rename_plan_session,
    friendly_video_names_enabled,
    new_webm_names_sorted_by_mtime,
    webm_basenames,
)
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
    primary_video: str | None = None
    e2e_session_videos: list[str] | None = None

    def to_json_dict(self) -> dict:
        d: dict = {
            "agent_version": __version__,
            "label": self.label,
            "start_url": self.start_url,
            "intent": self.intent,
            "units": [
                {"title": u.title, "href": u.href, "reason": u.reason or ""} for u in self.units
            ],
            "primary_video": self.primary_video,
            "e2e_session_videos": list(self.e2e_session_videos or []),
        }
        if self.trace_id:
            d["trace_id"] = self.trace_id
        if self.duration_ms is not None:
            d["duration_ms"] = self.duration_ms
        if self.walk_ranked_visits is not None:
            d["walk_ranked_visits"] = self.walk_ranked_visits
        return d


@dataclass
class OpenUnitRun:
    ok: bool
    opened_href: str | None
    ranked_unit_hrefs: list[str]
    visited_unit_hrefs: list[str]
    primary_video: str | None = None
    e2e_session_videos: list[str] | None = None


def _scroll_bottom_hold_ms() -> int:
    try:
        return max(800, int(os.environ.get("TRAILHEAD_RECORDING_SCROLL_BOTTOM_MS", "2800").strip()))
    except ValueError:
        return 2800


def reveal_trailhead_hands_on_ctas(page: Page) -> None:
    """
    Try to bring Trailhead Launch / Playground / hands-on controls into the viewport for .webm demos.

    This does not open a Salesforce org (still human-in-the-loop). Logged-in users usually see
    Launch / Playground text on module or unit pages; guests may see only login — nothing to fix in code.
    """
    if record_video_dir() is None:
        return
    v = os.environ.get("TRAILHEAD_RECORDING_PLAYGROUND_CTA_SCROLL", "1").strip().lower()
    if v in ("0", "false", "no", "off"):
        return
    name_rx = re.compile(
        r"launch|playground|hands[-\s]?on|trailhead\s*playground|open\s+trail|start\s+hands",
        re.I,
    )
    try:
        for role in ("link", "button"):
            loc = page.get_by_role(role, name=name_rx)
            n = loc.count()
            for i in range(min(n, 8)):
                try:
                    cell = loc.nth(i)
                    cell.scroll_into_view_if_needed(timeout=5000)
                    try:
                        cell.evaluate(
                            """e => {
  e.style.outline = '3px solid #0ea5e9';
  e.style.outlineOffset = '4px';
  e.style.transition = 'outline-color 0.2s ease';
  e.style.boxShadow = '0 0 0 4px rgba(14,165,233,0.28)';
}"""
                        )
                    except Exception:
                        pass
                    page.wait_for_timeout(1600)
                    try:
                        cell.evaluate(
                            """e => {
  e.style.outline = '';
  e.style.outlineOffset = '';
  e.style.boxShadow = '';
}"""
                        )
                    except Exception:
                        pass
                    logger.info(
                        "recording stage=playground_cta role=%s index=%d (scrolled into view)",
                        role,
                        i,
                    )
                    return
                except Exception:
                    continue
        for frac in (0.32, 0.5, 0.68, 0.88):
            try:
                jitter = frac + random.uniform(-0.04, 0.04)
                jitter = max(0.05, min(0.96, jitter))
                page.evaluate(
                    """fr => {
  const el = document.scrollingElement || document.documentElement;
  const max = Math.max(0, el.scrollHeight - el.clientHeight);
  window.scrollTo({ top: max * fr, behavior: 'smooth' });
}""",
                    jitter,
                )
                page.wait_for_timeout(random.randint(1100, 1700))
            except Exception as e:
                logger.debug("recording stagger scroll: %s", e)
    except Exception as e:
        logger.debug("reveal_trailhead_hands_on_ctas: %s", e)


def _scroll_demo_for_recording(page: Page) -> None:
    """Smooth scroll so Playwright recordings show something moving (discovery itself has no clicks)."""
    if not record_video_scroll_demo():
        return
    hold = _scroll_bottom_hold_ms()
    try:
        recording_humanish_scroll_down(page, chunks=5)
        page.evaluate("window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })")
        page.wait_for_timeout(hold)
        reveal_trailhead_hands_on_ctas(page)
        recording_scroll_toward_top(page, chunks=3)
        page.evaluate("window.scrollTo({ top: 0, behavior: 'smooth' })")
        page.wait_for_timeout(1000)
    except Exception as e:
        logger.debug("Recording scroll demo skipped: %s", e)


def org_prepare_recording_min_settle_ms() -> int:
    """Minimum post-navigation dwell for org prepare .webm (Trailhead LWC needs time to paint)."""
    try:
        v = int(os.environ.get("TRAILHEAD_ORG_PREPARE_RECORDING_MIN_MS", "5500").strip())
        return max(0, min(v, 120_000))
    except ValueError:
        return 5500


def plan_recording_tail_min_ms() -> int:
    """
    After plan title cards (and optional ranked walk), dwell on real Trailhead UI before the browser closes.
    Without this, plan-primary.webm often ends on a data-URL slide and feels cut off.
    """
    try:
        v = int(os.environ.get("TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS", "5500").strip())
        return max(0, min(v, 120_000))
    except ValueError:
        return 5500


def _plan_recording_epilogue(
    page: Page,
    *,
    start_url: str,
    walk_n: int,
    walk_visited: list[str],
) -> None:
    """When recording: show live Trailhead at the end so the .webm is not truncated on a title slide."""
    if record_video_dir() is None:
        return
    min_ms = plan_recording_tail_min_ms()
    nav_wait = "load"
    try:
        if walk_n > 0 and walk_visited:
            inject_recording_corner_tag(page, session="plan")
            settle_and_scroll_for_recording(page, min_settle_ms=min_ms)
        else:
            page.goto(start_url, wait_until=nav_wait, timeout=90_000)
            inject_recording_corner_tag(page, session="plan")
            settle_and_scroll_for_recording(page, min_settle_ms=min_ms)
        demo_recording_end_card(page, session="plan")
    except Exception as e:
        logger.warning("plan recording epilogue skipped: %s", e)
    try:
        page.wait_for_timeout(500)
    except Exception:
        pass


def settle_and_scroll_for_recording(page: Page, *, min_settle_ms: int | None = None) -> None:
    """
    When ``TRAILHEAD_RECORD_VIDEO_DIR`` is set: wait for the page to paint, then optional scroll demo.
    Used after org prepare navigation so clips are not a blank or spinner-only frame.
    """
    if record_video_dir() is None:
        return
    ms = _page_settle_ms()
    if min_settle_ms is not None:
        ms = max(ms, min_settle_ms)
    try:
        sw = trailhead_shell_wait_timeout_ms()
        if sw > 0:
            wait_for_trailhead_shell_ready(page, timeout_ms=sw)
        page.wait_for_timeout(ms)
    except Exception as e:
        logger.debug("settle_and_scroll_for_recording dwell: %s", e)
    reveal_trailhead_hands_on_ctas(page)
    _scroll_demo_for_recording(page)


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
        demo_before_walk_unit(
            page,
            index_one_based=i + 1,
            total=len(to_visit),
            title=u.title,
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
    demo_plan_what_you_asked(page, start_url=start_url, intent=intent, label=label)
    narrate_discovery_start(start_url=start_url)
    raw_units = collect_units_for_seed(page, start_url)
    narrate_discovery_done(
        candidate_count=len(raw_units),
        titles_sample=[u.title for u in raw_units[:40]],
    )
    _scroll_demo_for_recording(page)
    demo_after_discovery(page, candidate_count=len(raw_units))
    ranked = select_and_rank_units(intent=intent, candidates=raw_units)
    demo_llm_ranking_output_slide(page, intent=intent, units=ranked)
    demo_after_llm_rank(page, ranked_count=len(ranked), walk_will_visit=0)
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
    vroot = record_video_dir()
    before_webm = webm_basenames(vroot) if vroot else set()
    ranked: list[UnitRef] = []
    raw_count = 0
    walk_visited: list[str] = []
    elapsed_ms = 0
    with TrailheadBrowser(cfg) as br:
        page = br.page
        try_login(page, cfg.selectors)
        br.delay()
        demo_plan_what_you_asked(page, start_url=start_url, intent=intent, label=label)
        narrate_discovery_start(start_url=start_url)
        raw = collect_units_for_seed(page, start_url)
        raw_count = len(raw)
        narrate_discovery_done(
            candidate_count=raw_count,
            titles_sample=[u.title for u in raw[:40]],
        )
        _scroll_demo_for_recording(page)
        reveal_trailhead_hands_on_ctas(page)
        demo_after_discovery(page, candidate_count=len(raw))
        ranked = select_and_rank_units(intent=intent, candidates=raw)
        demo_llm_ranking_output_slide(page, intent=intent, units=ranked)
        demo_after_llm_rank(page, ranked_count=len(ranked), walk_will_visit=walk_n)
        if walk_n > 0 and ranked:
            walk_visited = walk_ranked_units_for_recording(page, ranked, max_visits=walk_n)
        narrate_plan_epilogue(start_url=start_url, walk_n=walk_n, walk_visited=len(walk_visited))
        _plan_recording_epilogue(
            page,
            start_url=start_url,
            walk_n=walk_n,
            walk_visited=walk_visited,
        )
        if record_video_dir() is not None:
            br.delay()
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Plan %r: %d units after LLM agent (%d raw links discovered) duration_ms=%d",
            label or start_url,
            len(ranked),
            raw_count,
            elapsed_ms,
        )
        if walk_n > 0:
            logger.info(
                "e2e_walk_ranked requested=%d visited_ok=%d",
                walk_n,
                len(walk_visited),
            )
        if log_units:
            for u in ranked[:20]:
                logger.info("  - %s | %s", u.title, u.href)
            if len(ranked) > 20:
                logger.info("  ... %d more", len(ranked) - 20)

    # Friendly rename only after context closes — Playwright keeps the .webm open until then (WinError 32).
    new_webms = new_webm_names_sorted_by_mtime(vroot, before_webm) if vroot else []
    pv: str | None = None
    if vroot and new_webms and friendly_video_names_enabled():
        new_webms, pv = friendly_rename_plan_session(vroot, new_webms)
    else:
        pv = choose_primary_webm(vroot, new_webms) if vroot and new_webms else None
    return RunPlan(
        label=label or start_url,
        start_url=start_url,
        intent=intent,
        units=ranked,
        trace_id=get_trace_id(),
        duration_ms=elapsed_ms,
        walk_ranked_visits=(len(walk_visited) if walk_n > 0 else None),
        primary_video=pv,
        e2e_session_videos=new_webms or None,
    )


def open_first_ranked_unit(
    cfg: AgentConfig,
    *,
    start_url: str,
    intent: str,
    label: str | None = None,
    visit_count: int = 1,
) -> OpenUnitRun:
    """Open the first ``visit_count`` LLM-ranked units in order (navigation only)."""
    start_url = validate_start_url(start_url)
    vc = max(1, _clamp_walk_count(visit_count))
    vroot = record_video_dir()
    before_webm = webm_basenames(vroot) if vroot else set()

    def _finish(
        ok: bool,
        opened: str | None,
        ranked: list[str],
        visited: list[str],
    ) -> OpenUnitRun:
        new_webms = new_webm_names_sorted_by_mtime(vroot, before_webm) if vroot else []
        pv: str | None = None
        if vroot and new_webms and friendly_video_names_enabled():
            new_webms, pv = friendly_rename_open_unit_session(vroot, new_webms)
        else:
            pv = choose_primary_webm(vroot, new_webms) if vroot and new_webms else None
        return OpenUnitRun(
            ok=ok,
            opened_href=opened,
            ranked_unit_hrefs=ranked,
            visited_unit_hrefs=visited,
            primary_video=pv,
            e2e_session_videos=new_webms or None,
        )

    finish_args: tuple[bool, str | None, list[str], list[str]] | None = None
    with TrailheadBrowser(cfg) as br:
        page = br.page
        try_login(page, cfg.selectors)
        br.delay()
        plan = build_plan(cfg, page, start_url=start_url, label=label or start_url, intent=intent)
        ranked = [u.href for u in plan.units]
        if not plan.units:
            logger.error("No units after LLM selection for %s", plan.start_url)
            finish_args = (False, None, ranked, [])
        else:
            n = min(vc, len(plan.units))
            visited_hrefs = walk_ranked_units_for_recording(page, plan.units, max_visits=n)
            if not visited_hrefs:
                logger.error("open-unit: no successful navigations among top %d ranked units", n)
                finish_args = (False, None, ranked, visited_hrefs)
            else:
                finish_args = (True, visited_hrefs[0], ranked, visited_hrefs)

    assert finish_args is not None
    ok, opened, ranked_hrefs, visited_hrefs = finish_args
    return _finish(ok, opened, ranked_hrefs, visited_hrefs)
