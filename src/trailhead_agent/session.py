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
        viewport: ViewportSize = {
            "width": self._cfg.browser.viewport_width,
            "height": self._cfg.browser.viewport_height,
        }
        hl = self._headless()
        video_dir = record_video_dir()
        if video_dir is not None:
            logger.info("Recording browser video under %s", video_dir)

        if profile is not None:
            profile.mkdir(parents=True, exist_ok=True)
            logger.info("Using persistent browser profile: %s", profile)
            if video_dir is not None:
                self._context = self._pw.chromium.launch_persistent_context(
                    str(profile),
                    headless=hl,
                    viewport=viewport,
                    record_video_dir=str(video_dir),
                    record_video_size=viewport,
                )
            else:
                self._context = self._pw.chromium.launch_persistent_context(
                    str(profile),
                    headless=hl,
                    viewport=viewport,
                )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        else:
            self._browser = self._pw.chromium.launch(headless=hl)
            if video_dir is not None:
                self._context = self._browser.new_context(
                    viewport=viewport,
                    record_video_dir=str(video_dir),
                    record_video_size=viewport,
                )
            else:
                self._context = self._browser.new_context(viewport=viewport)
            self._page = self._context.new_page()

        self._page.set_default_navigation_timeout(self._cfg.browser.navigation_timeout_ms)
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
