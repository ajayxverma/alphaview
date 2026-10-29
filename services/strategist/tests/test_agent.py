import pytest

from alphaview_strategist import agent

CLUSTER = {
    "label": "invoice reconciliation",
    "keywords": ["invoice reconciliation"],
    "excerpts": ["Is there a tool for this?"],
}
SCORED = {
    "gap_score": 72.5,
    "confidence": 0.6,
    "metrics": {
        "mentions": 40, "velocity": 1.8, "demand_intent_ratio": 0.55, "supply_ratio": 0.05,
        "sources": {"reddit": 40}, "external": {"search_volume": 12000},
    },
}


async def test_fallback_without_llm_key(monkeypatch):
    monkeypatch.setattr(agent, "_llm_available", lambda _model: False)
    strategy = await agent.synthesize("accounting firms", CLUSTER, SCORED)
    assert strategy.generated_by == "heuristic"
    assert "72.5" in strategy.thesis
    assert "12,000" in strategy.thesis


@pytest.mark.parametrize("field", ["execution_strategy", "risks", "kill_criteria", "key_takeaways"])
async def test_fallback_lists_populated(monkeypatch, field):
    monkeypatch.setattr(agent, "_llm_available", lambda _model: False)
    strategy = await agent.synthesize("q", CLUSTER, SCORED)
    assert getattr(strategy, field)
