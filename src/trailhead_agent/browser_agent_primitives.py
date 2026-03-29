"""
Browser automation helpers aligned with **Playwright** guidance:

- Prefer **locators** and built-in **auto-wait** / actionability over fixed sleeps for correctness.
- Use **explicit timeouts** on context/page so flaky pages fail predictably.
- Reserve **``wait_for_timeout``** for **recording pacing** and human-visible dwell (demo WebMs), not for
  asserting that content loaded — use **``wait_for_load_state``**, **``locator.wait_for``**, or
  **``expect``**-style checks where possible.

See: https://playwright.dev/docs/best-practices and https://playwright.dev/docs/actionability

This package does **not** implement deceptive bot evasion; use only on sites you are allowed to automate.
"""

from __future__ import annotations

import logging
import os
import random

from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger(__name__)


def apply_playwright_timeout_defaults(
    page: Page,
    context: BrowserContext,
    *,
    navigation_timeout_ms: int,
) -> None:
    """
    Mirror Playwright recommendations: one navigation budget for gotos, a bounded default for
    locator actions (clicks, fills, ``wait_for`` on locators).
    """
    nav = max(5_000, int(navigation_timeout_ms))
    loc = min(max(15_000, nav // 2), 60_000)
    try:
        context.set_default_navigation_timeout(nav)
    except Exception as e:
        logger.debug("set_default_navigation_timeout skipped: %s", e)
    try:
        page.set_default_navigation_timeout(nav)
    except Exception as e:
        logger.debug("page set_default_navigation_timeout skipped: %s", e)
    try:
        page.set_default_timeout(loc)
    except Exception as e:
        logger.debug("set_default_timeout skipped: %s", e)


def trailhead_shell_wait_timeout_ms() -> int:
    """Max time to wait for a coarse 'page has body content' signal after navigation (recording polish)."""
    try:
        v = int(os.environ.get("TRAILHEAD_SHELL_WAIT_TIMEOUT_MS", "12000").strip())
        return max(0, min(v, 60_000))
    except ValueError:
        return 12_000


def wait_for_trailhead_shell_ready(page: Page, *, timeout_ms: int | None = None) -> None:
    """
    Soft readiness wait using **locators** (not a blind sleep): ``main``, ``article``, or Lightning-ish roots.
    No-op if ``timeout_ms`` is 0 or every strategy misses (Trailhead DOM varies).
    """
    ms = trailhead_shell_wait_timeout_ms() if timeout_ms is None else max(0, timeout_ms)
    if ms <= 0:
        return
    selectors = (
        "main",
        "[role='main']",
        "article",
        ".slds-template__container",
        "[class*='trailhead']",
    )
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            loc.wait_for(state="attached", timeout=ms)
            logger.debug("trailhead shell signal ok selector=%s", sel)
            return
        except Exception:
            continue
    logger.debug("trailhead shell wait: no selector matched within %sms", ms)


def recording_humanish_scroll_down(page: Page, *, chunks: int = 5) -> None:
    """
    Varied ``scrollBy`` steps for demo recordings so motion looks less like a single linear jump.
    Uses only **page.evaluate** (no synthetic mouse pathing).
    """
    n = max(1, min(chunks, 12))
    for _ in range(n):
        try:
            frac_lo = 0.22 + random.random() * 0.08
            frac_hi = min(0.78, frac_lo + 0.18 + random.random() * 0.14)
            page.evaluate(
                """({ lo, hi }) => {
  const vh = window.innerHeight || 800;
  const frac = lo + Math.random() * Math.max(0.05, hi - lo);
  window.scrollBy({ top: vh * frac, behavior: 'smooth' });
}""",
                {"lo": frac_lo, "hi": frac_hi},
            )
            page.wait_for_timeout(random.randint(160, 380))
        except Exception as e:
            logger.debug("humanish scroll step skipped: %s", e)
            break


def recording_scroll_toward_top(page: Page, *, chunks: int = 3) -> None:
    """Smaller upward chunks toward the top (recording only)."""
    n = max(1, min(chunks, 8))
    for _ in range(n):
        try:
            frac = 0.25 + random.random() * 0.35
            page.evaluate(
                """fr => {
  const vh = window.innerHeight || 800;
  window.scrollBy({ top: -vh * fr, behavior: 'smooth' });
}""",
                frac,
            )
            page.wait_for_timeout(random.randint(120, 280))
        except Exception as e:
            logger.debug("humanish scroll up skipped: %s", e)
            break


def chromium_extra_launch_args() -> list[str]:
    """
    Optional extra Chromium flags (comma-separated in ``TRAILHEAD_CHROMIUM_EXTRA_ARGS``).
    Useful for CI (e.g. ``--disable-dev-shm-usage``) — not for deceptive fingerprint spoofing.
    """
    raw = os.environ.get("TRAILHEAD_CHROMIUM_EXTRA_ARGS", "").strip()
    if not raw:
        return []
    return [a.strip() for a in raw.split(",") if a.strip()]
