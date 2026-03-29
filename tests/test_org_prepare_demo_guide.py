from __future__ import annotations

from trailhead_agent.org_prepare_demo_guide import build_org_prepare_demo_guide


def test_demo_guide_has_core_keys() -> None:
    dg = build_org_prepare_demo_guide(start_url="https://trailhead.salesforce.com/x")
    assert dg["schema_version"] == 1
    assert "elevator_pitch" in dg
    assert "say_to_the_room" in dg and len(dg["say_to_the_room"]) >= 2
    assert "contrast_with_plan" in dg
    assert "try_next_commands" in dg
    assert "faq" in dg
    assert dg["this_run_start_url"] == "https://trailhead.salesforce.com/x"
