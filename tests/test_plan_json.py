from trailhead_agent.runner import RunPlan
from trailhead_agent.models import UnitRef


def test_run_plan_json_schema():
    p = RunPlan(
        label="L",
        start_url="https://trailhead.salesforce.com/content/learn/modules/x",
        intent="dev",
        units=[UnitRef(title="T", href="https://trailhead.salesforce.com/content/learn/modules/x/y")],
        trace_id="abc-123",
        duration_ms=42,
    )
    d = p.to_json_dict()
    assert set(d.keys()) >= {
        "agent_version",
        "label",
        "start_url",
        "intent",
        "units",
        "trace_id",
        "duration_ms",
    }
    assert d["trace_id"] == "abc-123"
    assert d["duration_ms"] == 42
    assert isinstance(d["units"], list)
    assert d["units"][0]["title"] == "T"
    assert d["units"][0]["href"].endswith("/y")
    assert d["units"][0]["reason"] == ""
