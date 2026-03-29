"""E2E JSON artifacts next to Playwright videos."""

import json

from trailhead_agent.e2e_artifacts import write_e2e_open_unit_output, write_e2e_plan_output
from trailhead_agent.models import UnitRef
from trailhead_agent.runner import RunPlan


def test_write_e2e_plan_output_creates_files(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    plan = RunPlan(
        label="test",
        start_url="https://trailhead.salesforce.com/content/learn/modules/x",
        intent="dev",
        units=[UnitRef(title="U", href="https://trailhead.salesforce.com/content/learn/modules/x/y")],
        trace_id="abc-123",
        duration_ms=99,
    )
    out = write_e2e_plan_output(plan)
    assert out is not None
    assert out.name == "e2e-plan-abc-123.json"
    latest = tmp_path / "e2e-plan-latest.json"
    assert latest.is_file()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["command"] == "plan"
    assert data["intent"] == "dev"
    assert data["duration_ms"] == 99
    assert len(data["units"]) == 1


def test_write_e2e_plan_includes_walk_ranked_visits(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    plan = RunPlan(
        label="test",
        start_url="https://trailhead.salesforce.com/content/learn/modules/x",
        intent="dev",
        units=[UnitRef(title="U", href="https://trailhead.salesforce.com/content/learn/modules/x/y")],
        trace_id="w-1",
        duration_ms=10,
        walk_ranked_visits=3,
    )
    write_e2e_plan_output(plan)
    data = json.loads((tmp_path / "e2e-plan-latest.json").read_text(encoding="utf-8"))
    assert data["walk_ranked_visits"] == 3


def test_write_e2e_open_unit_output(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    out = write_e2e_open_unit_output(
        start_url="https://trailhead.salesforce.com/content/learn/modules/x",
        intent="dev",
        label=None,
        success=True,
        opened_href="https://trailhead.salesforce.com/content/learn/modules/x/u1",
        ranked_unit_hrefs=["https://trailhead.salesforce.com/content/learn/modules/x/u1"],
    )
    assert out is not None
    assert (tmp_path / "e2e-open-unit-latest.json").is_file()


def test_write_e2e_open_unit_visit_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    h1 = "https://trailhead.salesforce.com/content/learn/modules/x/u1"
    h2 = "https://trailhead.salesforce.com/content/learn/modules/x/u2"
    write_e2e_open_unit_output(
        start_url="https://trailhead.salesforce.com/content/learn/modules/x",
        intent="dev",
        label=None,
        success=True,
        opened_href=h1,
        ranked_unit_hrefs=[h1, h2],
        visit_count=2,
        visited_unit_hrefs=[h1, h2],
    )
    data = json.loads((tmp_path / "e2e-open-unit-latest.json").read_text(encoding="utf-8"))
    assert data["visit_count"] == 2
    assert data["visited_unit_hrefs"] == [h1, h2]
