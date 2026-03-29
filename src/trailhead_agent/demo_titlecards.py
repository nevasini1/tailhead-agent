"""
Full-screen HTML title cards (data URLs) during Playwright recording so .webm demos
label phases (discovery, LLM, ranked walk, org workflow hints).

On by default whenever video recording is active (TRAILHEAD_RECORD_VIDEO_DIR / --artifacts-dir).
Set TRAILHEAD_DEMO_TITLECARDS=0 to disable. Optional dwell: TRAILHEAD_DEMO_TITLECARD_MS (default 2800).
"""

from __future__ import annotations

import base64
import html
import logging
import os

from playwright.sync_api import Page

from trailhead_agent.config import record_video_dir

logger = logging.getLogger(__name__)


def demo_titlecards_enabled() -> bool:
    """Explicit 1/0, or default **on** whenever Playwright is recording (see TRAILHEAD_RECORD_VIDEO_DIR)."""
    raw = os.environ.get("TRAILHEAD_DEMO_TITLECARDS", "").strip().lower()
    if raw in ("0", "false", "no", "off"):
        return False
    if raw in ("1", "true", "yes", "on"):
        return True
    return record_video_dir() is not None


def _dwell_ms() -> int:
    try:
        return max(800, int(os.environ.get("TRAILHEAD_DEMO_TITLECARD_MS", "2800")))
    except ValueError:
        return 2800


def show_demo_titlecard(page: Page, *, heading: str, lines: list[str]) -> None:
    """Navigate to a data-URL HTML slide; recorded in .webm when video is on."""
    if not demo_titlecards_enabled():
        return
    dwell = _dwell_ms()
    esc_heading = html.escape(heading)
    body = "".join(f"<p>{html.escape(line)}</p>" for line in lines)
    doc = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>{esc_heading}</title>
<style>
body{{font-family:system-ui,Segoe UI,sans-serif;background:linear-gradient(160deg,#0f172a,#1e293b);
color:#e2e8f0;margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
text-align:center;padding:2rem;box-sizing:border-box}}
.wrap{{max-width:42rem}}
h1{{font-size:clamp(1.25rem,4vw,1.85rem);font-weight:700;margin:0 0 1rem;line-height:1.25;
border-bottom:2px solid #38bdf8;padding-bottom:0.75rem}}
p{{font-size:clamp(0.95rem,2.2vw,1.15rem);line-height:1.5;margin:0.65rem 0;color:#cbd5e1}}
.badge{{display:inline-block;background:#0ea5e9;color:#0f172a;font-size:0.75rem;font-weight:700;
padding:0.2rem 0.55rem;border-radius:4px;margin-bottom:0.75rem}}
</style></head><body><div class="wrap"><div class="badge">trailhead-agent demo</div>
<h1>{esc_heading}</h1>{body}</div></body></html>"""
    b64 = base64.b64encode(doc.encode("utf-8")).decode("ascii")
    url = f"data:text/html;base64,{b64}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(dwell)
    except Exception as e:
        logger.debug("demo titlecard skipped: %s", e)


def demo_after_discovery(page: Page, *, candidate_count: int) -> None:
    show_demo_titlecard(
        page,
        heading="Phase 1 - Discovery (browser)",
        lines=[
            f"Collected {candidate_count} candidate unit links from Trailhead (DOM scrape).",
            "Ranking is not shown in the browser - the LLM runs next over the network.",
        ],
    )


def demo_after_llm_rank(page: Page, *, ranked_count: int, walk_will_visit: int) -> None:
    if walk_will_visit > 0:
        lines = [
            f"Phase 2 - LLM ranked {ranked_count} units for your intent.",
            f"Next in this recording: visit the top {walk_will_visit} ranked URLs in order (navigation only).",
            "After your run: trailhead-agent org checklist --plan-json …e2e-plan-latest.json",
        ]
    else:
        lines = [
            f"Phase 2 - LLM ranked {ranked_count} units for your intent.",
            "Use trailhead-agent org checklist --plan-json …e2e-plan-latest.json for Playground / org steps.",
        ]
    show_demo_titlecard(page, heading="Phase 2 - LLM ranking complete", lines=lines)


def demo_before_walk_unit(page: Page, *, index_one_based: int, total: int, title: str) -> None:
    show_demo_titlecard(
        page,
        heading=f"Phase 3 - Ranked walk {index_one_based} / {total}",
        lines=[
            title,
            "Opening this Trailhead unit in the browser (human-in-the-loop in the real org).",
            "Org checklist: trailhead-agent org checklist --unit-href <this unit URL>",
        ],
    )


def demo_org_prepare_browser(page: Page) -> None:
    show_demo_titlecard(
        page,
        heading="Org prepare - Trailhead (browser)",
        lines=[
            "Opening the Trailhead page so you can Launch Playground / sign in yourself.",
            "This tool does not auto-complete challenges or quizzes.",
        ],
    )
