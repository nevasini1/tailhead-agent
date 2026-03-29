from __future__ import annotations

from trailhead_agent import demo_titlecards


def test_demo_titlecards_explicit_off(monkeypatch, tmp_path):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    monkeypatch.setenv("TRAILHEAD_DEMO_TITLECARDS", "0")
    assert demo_titlecards.demo_titlecards_enabled() is False


def test_demo_titlecards_explicit_on_without_recording(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_RECORD_VIDEO_DIR", raising=False)
    monkeypatch.delenv("TRAILHEAD_DEMO_TITLECARDS", raising=False)
    monkeypatch.setenv("TRAILHEAD_DEMO_TITLECARDS", "1")
    assert demo_titlecards.demo_titlecards_enabled() is True


def test_demo_titlecards_auto_on_when_recording(monkeypatch, tmp_path):
    monkeypatch.delenv("TRAILHEAD_DEMO_TITLECARDS", raising=False)
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    assert demo_titlecards.demo_titlecards_enabled() is True


def test_demo_titlecards_default_off_without_recording(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_RECORD_VIDEO_DIR", raising=False)
    monkeypatch.delenv("TRAILHEAD_DEMO_TITLECARDS", raising=False)
    assert demo_titlecards.demo_titlecards_enabled() is False
