from __future__ import annotations

import logging
import time
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, ViewportSize, sync_playwright

from trailhead_agent.config import (
    AgentConfig,
    action_delay_ms,
    headless_mode,
    persistent_profile_dir,
    record_video_dir,
)
from trailhead_agent.browser_agent_primitives import (
    apply_playwright_timeout_defaults,
    chromium_extra_launch_args,
)
from trailhead_agent.demo_browser import demo_slow_mo_ms, demo_viewport_dimensions

logger = logging.getLogger(__name__)


class TrailheadBrowser:
    def __init__(self, cfg: AgentConfig, *, force_visible: bool = False) -> None:
        self._cfg = cfg
        self._force_visible = force_visible
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def _headless(self) -> bool:
        if self._force_visible:
            return False
        return headless_mode(self._cfg)

    def __enter__(self) -> "TrailheadBrowser":
        self._pw = sync_playwright().start()
        profile = persistent_profile_dir()
        vw, vh = demo_viewport_dimensions(
            self._cfg.browser.viewport_width,
            self._cfg.browser.viewport_height,
        )
        viewport: ViewportSize = {"width": vw, "height": vh}
        hl = self._headless()
        video_dir = record_video_dir()
        slow_mo = demo_slow_mo_ms()
        if slow_mo:
            logger.info("Playwright slow_mo=%dms (demo / TRAILHEAD_DEMO_SLOW_MO_MS)", slow_mo)
        if video_dir is not None:
            logger.info("Recording browser video under %s", video_dir)
        ch_args = chromium_extra_launch_args()

        if profile is not None:
            profile.mkdir(parents=True, exist_ok=True)
            logger.info("Using persistent browser profile: %s", profile)
            if video_dir is not None:
                self._context = self._pw.chromium.launch_persistent_context(
                    str(profile),
                    headless=hl,
                    viewport=viewport,
                    slow_mo=slow_mo,
                    args=ch_args,
                    record_video_dir=str(video_dir),
                    record_video_size=viewport,
                )
            else:
                self._context = self._pw.chromium.launch_persistent_context(
                    str(profile),
                    headless=hl,
                    viewport=viewport,
                    slow_mo=slow_mo,
                    args=ch_args,
                )
            # One browser tab = one .webm when recording; restored multi-tab profiles would
            # otherwise emit multiple videos per session.
            if video_dir is not None:
                pages = list(self._context.pages)
                n0 = len(pages)
                for p in pages:
                    try:
                        p.close()
                    except Exception as e:
                        logger.debug("close extra persistent page: %s", e)
                self._page = self._context.new_page()
                if n0 > 1:
                    logger.warning(
                        "Recording with a persistent profile that had %d open tab(s). "
                        "Closed them before this run; Playwright may still write short extra .webm files. "
                        "Use e2e JSON fields primary_video and video_files (role=primary) for the main clip.",
                        n0,
                    )
            else:
                self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        else:
            self._browser = self._pw.chromium.launch(headless=hl, slow_mo=slow_mo, args=ch_args)
            if video_dir is not None:
                self._context = self._browser.new_context(
                    viewport=viewport,
                    record_video_dir=str(video_dir),
                    record_video_size=viewport,
                )
            else:
                self._context = self._browser.new_context(viewport=viewport)
            self._page = self._context.new_page()

        apply_playwright_timeout_defaults(
            self._page,
            self._context,
            navigation_timeout_ms=self._cfg.browser.navigation_timeout_ms,
        )
        return self

    def __exit__(self, *args: Any) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    @property
    def page(self) -> Page:
        if not self._page:
            raise RuntimeError("Browser not started; use 'with TrailheadBrowser(cfg):'")
        return self._page

    def delay(self) -> None:
        ms = action_delay_ms()
        if ms:
            time.sleep(ms / 1000.0)
