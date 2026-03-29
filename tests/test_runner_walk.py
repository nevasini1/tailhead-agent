"""Ranked URL walk for E2E recordings (navigation only)."""

from unittest.mock import MagicMock

from trailhead_agent.models import UnitRef
from trailhead_agent.runner import (
    _plan_recording_epilogue,
    plan_recording_tail_min_ms,
    walk_ranked_units_for_recording,
)


def test_walk_ranked_visits_each_href_in_order(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_RECORD_VIDEO_DIR", raising=False)
    monkeypatch.setenv("TRAILHEAD_DEMO_TITLECARDS", "0")
    page = MagicMock()
    u1 = UnitRef(
        title="A",
        href="https://trailhead.salesforce.com/content/learn/modules/m/u1",
    )
    u2 = UnitRef(
        title="B",
        href="https://trailhead.salesforce.com/content/learn/modules/m/u2",
    )
    out = walk_ranked_units_for_recording(page, [u1, u2], max_visits=2)
    assert out == [u1.href, u2.href]
    assert page.goto.call_count == 2


def test_walk_ranked_zero_is_noop():
    page = MagicMock()
    u = UnitRef(
        title="A",
        href="https://trailhead.salesforce.com/content/learn/modules/m/u1",
    )
    assert walk_ranked_units_for_recording(page, [u], max_visits=0) == []
    page.goto.assert_not_called()


def test_plan_recording_tail_min_ms_default(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS", raising=False)
    assert plan_recording_tail_min_ms() == 5500


def test_plan_epilogue_navigates_to_start_when_no_walk(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    monkeypatch.setenv("TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS", "0")
    monkeypatch.setenv("TRAILHEAD_DEMO_END_CARD_MS", "0")
    page = MagicMock()
    su = "https://trailhead.salesforce.com/content/learn/modules/x"
    _plan_recording_epilogue(page, start_url=su, walk_n=0, walk_visited=[])
    assert page.goto.call_count >= 2
    assert su in str(page.goto.call_args_list[0])
    assert "data:text/html" in str(page.goto.call_args_list[-1])


def test_plan_epilogue_no_trailhead_goto_when_walk_succeeded(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    monkeypatch.setenv("TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS", "0")
    monkeypatch.setenv("TRAILHEAD_DEMO_END_CARD_MS", "0")
    page = MagicMock()
    su = "https://trailhead.salesforce.com/content/learn/modules/x"
    visited = ["https://trailhead.salesforce.com/content/learn/modules/x/u1"]
    _plan_recording_epilogue(page, start_url=su, walk_n=1, walk_visited=visited)
    for call in page.goto.call_args_list:
        assert "trailhead.salesforce.com" not in str(call)
    assert page.goto.call_count >= 1
    assert "data:text/html" in str(page.goto.call_args_list[-1])
