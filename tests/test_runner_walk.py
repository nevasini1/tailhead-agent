"""Ranked URL walk for E2E recordings (navigation only)."""

from unittest.mock import MagicMock

from trailhead_agent.models import UnitRef
from trailhead_agent.runner import walk_ranked_units_for_recording


def test_walk_ranked_visits_each_href_in_order():
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
