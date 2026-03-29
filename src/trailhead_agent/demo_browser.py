"""
Browser defaults for recorded E2E demos (plan / open-unit / org prepare + video).

When ``TRAILHEAD_RECORD_VIDEO_DIR`` is set, optional **auto demo** mode improves watchability:
headed Chromium (unless you already set ``TRAILHEAD_AGENT_HEADLESS``), Playwright ``slow_mo``,
slightly larger viewport, and a small action delay — without changing ranking or discovery logic.

Disable for CI: ``TRAILHEAD_RECORDING_DEMO_AUTO=0`` or ``plan --no-recording-demo-browser``.
"""

from __future__ import annotations

import os

from trailhead_agent.config import record_video_dir


def recording_demo_auto_enabled() -> bool:
    """Extra demo polish when recording, unless opted out."""
    if record_video_dir() is None:
        return False
    v = os.environ.get("TRAILHEAD_RECORDING_DEMO_AUTO", "1").strip().lower()
    return v not in ("0", "false", "no", "off")


def bootstrap_recording_demo_environment() -> None:
    """
    Set env defaults once per process before ``load_config`` / browser start.
    Does not override variables the user already exported.
    """
    if not recording_demo_auto_enabled():
        return
    if "TRAILHEAD_AGENT_HEADLESS" not in os.environ:
        os.environ["TRAILHEAD_AGENT_HEADLESS"] = "0"
    if "TRAILHEAD_DEMO_SLOW_MO_MS" not in os.environ:
        os.environ["TRAILHEAD_DEMO_SLOW_MO_MS"] = "65"
    if "TRAILHEAD_DEMO_VIEWPORT_WIDTH" not in os.environ:
        os.environ["TRAILHEAD_DEMO_VIEWPORT_WIDTH"] = "1440"
    if "TRAILHEAD_DEMO_VIEWPORT_HEIGHT" not in os.environ:
        os.environ["TRAILHEAD_DEMO_VIEWPORT_HEIGHT"] = "900"
    if "AGENT_ACTION_DELAY_MS" not in os.environ:
        os.environ["AGENT_ACTION_DELAY_MS"] = "100"
    if "TRAILHEAD_RECORDING_SCROLL_BOTTOM_MS" not in os.environ:
        os.environ["TRAILHEAD_RECORDING_SCROLL_BOTTOM_MS"] = "3200"


def demo_slow_mo_ms() -> int:
    try:
        return max(0, min(800, int(os.environ.get("TRAILHEAD_DEMO_SLOW_MO_MS", "0").strip())))
    except ValueError:
        return 0


def demo_viewport_dimensions(cfg_width: int, cfg_height: int) -> tuple[int, int]:
    """Return (width, height) honoring TRAILHEAD_DEMO_VIEWPORT_* when recording demo auto is on."""
    w, h = cfg_width, cfg_height
    if not recording_demo_auto_enabled():
        return w, h
    try:
        ew = int(os.environ.get("TRAILHEAD_DEMO_VIEWPORT_WIDTH", str(w)).strip())
        w = max(400, min(3840, ew))
    except ValueError:
        pass
    try:
        eh = int(os.environ.get("TRAILHEAD_DEMO_VIEWPORT_HEIGHT", str(h)).strip())
        h = max(400, min(2160, eh))
    except ValueError:
        pass
    return w, h
