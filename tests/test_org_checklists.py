import json
from pathlib import Path

import pytest

from trailhead_agent.org_checklists import (
    checklist_json_list,
    load_checklist_registry,
    module_slug_from_href,
    resolve_checklist_for_context,
)
from trailhead_agent.org_executor import TrailheadUnitContext


def test_module_slug_from_href():
    assert (
        module_slug_from_href(
            "https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_intro"
        )
        == "apex_database"
    )
    assert module_slug_from_href("https://example.com/nope") is None


def test_resolve_apex_database(checklists_path: Path):
    ctx = TrailheadUnitContext(
        title="Intro",
        href="https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_intro",
    )
    steps, key = resolve_checklist_for_context(ctx, registry_path=checklists_path)
    assert key == "apex_database"
    assert len(steps) >= 2
    assert steps[0].step_id == "launch_playground"


def test_resolve_reports_dashboards(checklists_path: Path):
    ctx = TrailheadUnitContext(
        title="Reports",
        href="https://trailhead.salesforce.com/content/learn/modules/reports_dashboards/foo_unit",
    )
    steps, key = resolve_checklist_for_context(ctx, registry_path=checklists_path)
    assert key == "reports_dashboards"
    assert any("Reports" in s.description for s in steps)


def test_resolve_unknown_uses_default(checklists_path: Path):
    ctx = TrailheadUnitContext(
        title="X",
        href="https://trailhead.salesforce.com/content/learn/modules/unknown_module_xyz/unit_a",
    )
    steps, key = resolve_checklist_for_context(ctx, registry_path=checklists_path)
    assert key == "default"
    assert len(steps) >= 1


def test_load_units_from_plan_json(tmp_path: Path):
    from trailhead_agent.org_commands import load_units_from_plan_json

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "units": [
                    {
                        "title": "T",
                        "href": "https://trailhead.salesforce.com/content/learn/modules/apex_database/u",
                    },
                ]
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    units = load_units_from_plan_json(plan_path)
    assert len(units) == 1
    assert "apex_database" in units[0]["href"]


@pytest.fixture
def checklists_path() -> Path:
    root = Path(__file__).resolve().parents[1]
    p = root / "config" / "org_checklists.yaml"
    assert p.is_file()
    return p


def test_registry_loads(checklists_path: Path):
    reg = load_checklist_registry(checklists_path)
    assert "checklists_by_module" in reg
    assert "apex_database" in reg["checklists_by_module"]


def test_checklist_json_list_roundtrip():
    from trailhead_agent.org_executor import OrgStep

    s = [OrgStep(step_id="a", description="d", verification="manual")]
    assert checklist_json_list(s)[0]["step_id"] == "a"
