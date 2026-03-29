from __future__ import annotations

from unittest.mock import MagicMock

from trailhead_agent.browser_agent_primitives import (
    apply_playwright_timeout_defaults,
    chromium_extra_launch_args,
    recording_humanish_scroll_down,
    trailhead_shell_wait_timeout_ms,
    wait_for_trailhead_shell_ready,
)


def test_apply_playwright_timeout_defaults_calls_context_and_page(monkeypatch):
    page = MagicMock()
    ctx = MagicMock()
    apply_playwright_timeout_defaults(page, ctx, navigation_timeout_ms=45_000)
    ctx.set_default_navigation_timeout.assert_called_once_with(45_000)
    page.set_default_navigation_timeout.assert_called_once_with(45_000)
    page.set_default_timeout.assert_called_once()


def test_chromium_extra_launch_args_empty():
    assert chromium_extra_launch_args() == []


def test_chromium_extra_launch_args_parses(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_CHROMIUM_EXTRA_ARGS", " --a , --b ")
    assert chromium_extra_launch_args() == ["--a", "--b"]


def test_trailhead_shell_wait_timeout_ms(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_SHELL_WAIT_TIMEOUT_MS", raising=False)
    assert trailhead_shell_wait_timeout_ms() == 12_000
    monkeypatch.setenv("TRAILHEAD_SHELL_WAIT_TIMEOUT_MS", "0")
    assert trailhead_shell_wait_timeout_ms() == 0


def test_wait_for_trailhead_shell_ready_noop_zero_timeout():
    page = MagicMock()
    wait_for_trailhead_shell_ready(page, timeout_ms=0)
    page.locator.assert_not_called()


def test_recording_humanish_scroll_down_runs_evaluate():
    page = MagicMock()
    recording_humanish_scroll_down(page, chunks=2)
    assert page.evaluate.call_count == 2
    assert page.wait_for_timeout.call_count == 2
