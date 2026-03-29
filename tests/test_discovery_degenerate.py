from __future__ import annotations

from trailhead_agent.discovery import _units_look_degenerate
from trailhead_agent.models import UnitRef


def test_degenerate_all_trivial_titles() -> None:
    units = [UnitRef(title=" ", href=f"https://trailhead.salesforce.com/content/learn/modules/x/u{i}") for i in range(3)]
    msg = _units_look_degenerate(units)
    assert msg is not None
    assert "trivial" in msg.lower() or "empty" in msg.lower()


def test_degenerate_duplicate_title_majority() -> None:
    units = [UnitRef(title="Same", href=f"https://trailhead.salesforce.com/content/learn/modules/x/u{i}") for i in range(6)]
    msg = _units_look_degenerate(units)
    assert msg is not None
    assert "same" in msg.lower()


def test_degenerate_none_for_diverse_titles() -> None:
    units = [
        UnitRef(title=f"Unit {i}", href=f"https://trailhead.salesforce.com/content/learn/modules/x/u{i}")
        for i in range(5)
    ]
    assert _units_look_degenerate(units) is None
