from trailhead_agent.llm_agent import apply_llm_ranking
from trailhead_agent.models import UnitRef


def test_apply_llm_ranking_filters_unknown_hrefs():
    a = UnitRef(title="A", href="https://trailhead.salesforce.com/content/learn/modules/m/u1")
    b = UnitRef(title="B", href="https://trailhead.salesforce.com/content/learn/modules/m/u2")
    data = {
        "ordered_units": [
            {"href": b.href, "title": b.title, "reason": "x"},
            {"href": "https://trailhead.salesforce.com/fake", "title": "nope", "reason": "y"},
            {"href": a.href, "title": a.title, "reason": "z"},
        ]
    }
    out = apply_llm_ranking(data, [a, b])
    assert [u.href for u in out] == [b.href, a.href]


def test_apply_llm_ranking_bad_shape_falls_back_empty():
    a = UnitRef(title="A", href="https://trailhead.salesforce.com/content/learn/modules/m/u1")
    assert apply_llm_ranking({"ordered_units": "nope"}, [a]) == []
