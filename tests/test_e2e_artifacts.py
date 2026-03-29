"""E2E JSON artifacts next to Playwright videos."""

import json

from trailhead_agent.e2e_artifacts import (
    choose_primary_webm,
    friendly_rename_plan_session,
    other_webms_in_dir,
    write_e2e_open_unit_output,
    write_e2e_plan_output,
)
from trailhead_agent.models import UnitRef
from trailhead_agent.runner import RunPlan


def test_friendly_rename_plan_session_orders_primary_first(tmp_path):
    (tmp_path / "aa.webm").write_bytes(b"x")
    (tmp_path / "bb.webm").write_bytes(b"x" * 200)
    new_names, primary = friendly_rename_plan_session(tmp_path, ["aa.webm", "bb.webm"])
    assert primary == "plan-primary.webm"
    assert set(new_names) == {"plan-primary.webm", "plan-session-01.webm"}
    assert (tmp_path / "plan-primary.webm").is_file()
    assert (tmp_path / "plan-session-01.webm").is_file()


def test_choose_primary_webm_picks_largest(tmp_path):
    (tmp_path / "small.webm").write_bytes(b"x")
    (tmp_path / "big.webm").write_bytes(b"x" * 100)
    assert choose_primary_webm(tmp_path, ["small.webm", "big.webm"]) == "big.webm"


def test_other_webms_in_dir_excludes_session(tmp_path):
    (tmp_path / "a.webm").write_bytes(b"1")
    (tmp_path / "b.webm").write_bytes(b"2")
    other = other_webms_in_dir(tmp_path, {"a.webm"})
    names = [r["name"] for r in other]
    assert "a.webm" not in names
    assert "b.webm" in names


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
    assert "primary_video" in data
    assert data["e2e_session_videos"] == []
    assert data["video_files"] == []
    assert "video_files_other_in_dir" in data
    man = tmp_path / "e2e-manifest.json"
    assert man.is_file()
    mdoc = json.loads(man.read_text(encoding="utf-8"))
    assert mdoc["version"] == 1
    assert len(mdoc["recordings"]) == 1
    assert mdoc["recordings"][0]["source"] == "plan"
    viewer = tmp_path / "e2e-report.html"
    assert viewer.is_file()
    assert "trailhead-agent" in viewer.read_text(encoding="utf-8")


def test_write_e2e_plan_output_video_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("TRAILHEAD_RECORD_VIDEO_DIR", str(tmp_path))
    (tmp_path / "small.webm").write_bytes(b"ab")
    (tmp_path / "large.webm").write_bytes(b"x" * 80)
    plan = RunPlan(
        label="test",
        start_url="https://trailhead.salesforce.com/content/learn/modules/x",
        intent="dev",
        units=[UnitRef(title="U", href="https://trailhead.salesforce.com/content/learn/modules/x/y")],
        trace_id="vid-1",
        duration_ms=10,
        primary_video="large.webm",
        e2e_session_videos=["small.webm", "large.webm"],
    )
    write_e2e_plan_output(plan)
    data = json.loads((tmp_path / "e2e-plan-latest.json").read_text(encoding="utf-8"))
    by_name = {r["name"]: r["role"] for r in data["video_files"]}
    assert by_name["large.webm"] == "primary"
    assert by_name["small.webm"] == "session"


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
