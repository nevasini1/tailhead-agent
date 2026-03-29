from __future__ import annotations

from trailhead_agent import demo_titlecards
from trailhead_agent.models import UnitRef


def test_ranked_units_body_html_escapes_and_truncates_reason(monkeypatch):
    monkeypatch.setenv("TRAILHEAD_DEMO_TITLECARD_RANK_MAX", "5")
    units = [
        UnitRef(title='A & <b>', href="https://x", reason="y" * 200),
        UnitRef(title="B", href="https://y"),
    ]
    html_out = demo_titlecards._ranked_units_body_html(units, intent='Say "hi"')
    assert "A &amp;" in html_out
    assert "&lt;b&gt;" in html_out
    assert "<b>" not in html_out
    assert "Say &quot;hi&quot;" in html_out
    assert "\u2026" in html_out  # reason truncated past 120 chars


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
