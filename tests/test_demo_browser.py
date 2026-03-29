from __future__ import annotations

import os

import pytest

from trailhead_agent import demo_browser as db


def test_recording_demo_auto_off_without_video_dir(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_RECORD_VIDEO_DIR", raising=False)
    assert db.recording_demo_auto_enabled() is False


def test_bootstrap_sets_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    monkeypatch.delenv("TRAILHEAD_RECORDING_DEMO_AUTO", raising=False)
    for k in (
        "TRAILHEAD_AGENT_HEADLESS",
        "TRAILHEAD_DEMO_SLOW_MO_MS",
        "TRAILHEAD_DEMO_VIEWPORT_WIDTH",
        "TRAILHEAD_DEMO_VIEWPORT_HEIGHT",
        "AGENT_ACTION_DELAY_MS",
        "TRAILHEAD_RECORDING_SCROLL_BOTTOM_MS",
    ):
        monkeypatch.delenv(k, raising=False)
    db.bootstrap_recording_demo_environment()
    assert os.environ.get("TRAILHEAD_AGENT_HEADLESS") == "0"
    assert os.environ.get("TRAILHEAD_DEMO_SLOW_MO_MS") == "65"
    assert os.environ.get("TRAILHEAD_DEMO_VIEWPORT_WIDTH") == "1440"
    assert os.environ.get("TRAILHEAD_DEMO_VIEWPORT_HEIGHT") == "900"
    assert os.environ.get("AGENT_ACTION_DELAY_MS") == "100"


def test_bootstrap_respects_existing_headless(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    monkeypatch.setenv("TRAILHEAD_AGENT_HEADLESS", "1")
    monkeypatch.delenv("TRAILHEAD_RECORDING_DEMO_AUTO", raising=False)
    db.bootstrap_recording_demo_environment()
    assert os.environ.get("TRAILHEAD_AGENT_HEADLESS") == "1"


def test_bootstrap_skips_when_demo_auto_off(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    monkeypatch.setenv("TRAILHEAD_RECORDING_DEMO_AUTO", "0")
    monkeypatch.delenv("TRAILHEAD_DEMO_SLOW_MO_MS", raising=False)
    db.bootstrap_recording_demo_environment()
    assert "TRAILHEAD_DEMO_SLOW_MO_MS" not in os.environ


@pytest.mark.parametrize(
    ("auto", "w", "h", "exp_w", "exp_h"),
    [
        (False, 1280, 800, 1280, 800),
        (True, 1280, 800, 1440, 900),
    ],
)
def test_demo_viewport_dimensions(tmp_path, monkeypatch, auto, w, h, exp_w, exp_h):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    if auto:
        monkeypatch.delenv("TRAILHEAD_RECORDING_DEMO_AUTO", raising=False)
        monkeypatch.setenv("TRAILHEAD_DEMO_VIEWPORT_WIDTH", "1440")
        monkeypatch.setenv("TRAILHEAD_DEMO_VIEWPORT_HEIGHT", "900")
    else:
        monkeypatch.setenv("TRAILHEAD_RECORDING_DEMO_AUTO", "0")
    assert db.demo_viewport_dimensions(w, h) == (exp_w, exp_h)
