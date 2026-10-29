from alphaview_discovery.gap import score_gap

CLUSTER = {
    "label": "x", "keywords": ["invoice tool"], "size": 30, "engagement": 300, "velocity": 1.5,
    "neg_sentiment": 0.3, "demand_ratio": 0.6, "complaint_ratio": 0.3, "supply_ratio": 0.05,
    "unanswered_ratio": 0.4, "sources": {"reddit": 30},
}


def test_score_bounds():
    s = score_gap(CLUSTER, {}, [])
    assert 0 <= s["gap_score"] <= 100
    assert 0 <= s["confidence"] <= 1


def test_external_metrics_raise_score():
    base = score_gap(CLUSTER, {}, [])
    boosted = score_gap(CLUSTER, {"invoice tool": {"search_volume": 50000, "trend_growth": 0.8}}, ["dataforseo"])
    assert boosted["gap_score"] > base["gap_score"]
    assert boosted["confidence"] > base["confidence"]


def test_supply_lowers_score():
    crowded = {**CLUSTER, "supply_ratio": 0.6}
    assert score_gap(crowded, {}, [])["gap_score"] < score_gap(CLUSTER, {}, [])["gap_score"]
