from unittest.mock import MagicMock, patch

from trailhead_agent.cli_org_executor import (
    CliOrgExecutor,
    org_display_says_connected,
    run_sf_org_display_json,
)
from trailhead_agent.org_executor import OrgStep, TrailheadUnitContext


def test_org_display_says_connected_username():
    assert org_display_says_connected({"status": 0, "result": {"username": "a@b.com"}})


def test_org_display_says_connected_bad_status():
    assert not org_display_says_connected({"status": 1, "result": {}})


def test_run_sf_org_display_json_mock():
    fake = MagicMock()
    fake.returncode = 0
    fake.stdout = '{"status":0,"result":{"username":"u@x"}}'
    fake.stderr = ""
    with patch("trailhead_agent.cli_org_executor.subprocess.run", return_value=fake):
        code, data, err = run_sf_org_display_json(org_alias="myalias")
    assert code == 0
    assert isinstance(data, dict)
    assert data.get("result", {}).get("username") == "u@x"


def test_cli_executor_manual_step():
    ex = CliOrgExecutor()
    ctx = TrailheadUnitContext(title="t", href="https://trailhead.salesforce.com/content/learn/modules/x/y")
    step = OrgStep(step_id="1", description="d", verification="manual")
    r = ex.execute_step(ctx, step)
    assert r.ok is True


def test_cli_executor_propose_steps_uses_yaml(tmp_path):
    yml = tmp_path / "c.yaml"
    yml.write_text(
        """
checklists_by_module:
  mymod:
    - step_id: s1
      description: Do the thing
      verification: manual
default_module_steps: []
""",
        encoding="utf-8",
    )
    ex = CliOrgExecutor(checklist_config=yml)
    ctx = TrailheadUnitContext(
        title="U",
        href="https://trailhead.salesforce.com/content/learn/modules/mymod/unit1",
    )
    steps = ex.propose_steps(ctx)
    assert len(steps) == 1
    assert steps[0].step_id == "s1"
