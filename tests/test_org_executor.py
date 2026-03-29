from trailhead_agent.org_executor import (
    NoopOrgExecutor,
    OrgStep,
    OrgStepResult,
    TrailheadUnitContext,
    get_default_org_executor,
)


def test_noop_executor_contract():
    ex = NoopOrgExecutor()
    ctx = TrailheadUnitContext(title="Unit", href="https://trailhead.salesforce.com/m/u")
    assert ex.ensure_playground_ready(ctx) is False
    assert ex.propose_steps(ctx) == []
    step = OrgStep(step_id="1", description="open dev console", verification="manual")
    res = ex.execute_step(ctx, step)
    assert isinstance(res, OrgStepResult)
    assert res.ok is False


def test_default_factory_returns_noop(monkeypatch):
    monkeypatch.delenv("TRAILHEAD_ORG_EXECUTOR", raising=False)
    assert isinstance(get_default_org_executor(), NoopOrgExecutor)


def test_default_factory_cli_when_env(monkeypatch):
    from trailhead_agent.cli_org_executor import CliOrgExecutor

    monkeypatch.setenv("TRAILHEAD_ORG_EXECUTOR", "cli")
    assert isinstance(get_default_org_executor(), CliOrgExecutor)
    monkeypatch.setenv("TRAILHEAD_ORG_EXECUTOR", "noop")
