import json
from pathlib import Path

from trailhead_agent.llm_agent import apply_llm_ranking
from trailhead_agent.models import UnitRef

FIXTURE = Path(__file__).parent / "fixtures" / "llm_apex_rank.json"


def test_golden_fixture_order_and_filtering():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    candidates = [
        UnitRef(
            title="Get Started with Apex",
            href="https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_intro",
        ),
        UnitRef(
            title="Write SOQL Queries",
            href="https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_soql",
        ),
        UnitRef(
            title="Extra",
            href="https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_dml",
        ),
    ]
    out = apply_llm_ranking(data, candidates)
    assert [u.href for u in out] == [
        "https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_soql",
        "https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_intro",
    ]
