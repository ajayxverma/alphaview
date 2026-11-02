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


LLM = {"model": "groq/llama-3.3-70b-versatile", "api_key": "gsk_secret"}


async def test_fallback_without_llm(monkeypatch):
    strategy = await agent.synthesize("accounting firms", CLUSTER, SCORED, None)
    assert strategy.generated_by == "heuristic"
    assert "72.5" in strategy.thesis
    assert "12,000" in strategy.thesis


@pytest.mark.parametrize("field", ["execution_strategy", "risks", "kill_criteria", "key_takeaways"])
async def test_fallback_lists_populated(field):
    strategy = await agent.synthesize("q", CLUSTER, SCORED, None)
    assert getattr(strategy, field)


def test_blank_api_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert not agent._llm_available("gpt-4o-mini")
    assert agent.server_default_llm() is None


async def test_provider_error_falls_back(monkeypatch):
    async def boom(**_kwargs):
        raise agent.litellm.exceptions.InternalServerError(
            message="Missing credentials", llm_provider="openai", model="gpt-4o-mini"
        )

    monkeypatch.setattr(agent.litellm, "acompletion", boom)
    strategy = await agent.synthesize("q", CLUSTER, SCORED, LLM)
    assert strategy.generated_by == "heuristic"
    assert strategy.model == LLM["model"]
    assert "request failed" in strategy.fallback_reason
    assert "no LLM configured" not in strategy.risks[0]


async def test_json_mode_failure_retries_without_response_format(monkeypatch):
    calls = []
    strategy_json = agent._fallback("q", CLUSTER, SCORED).model_dump_json()

    async def completion(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise agent.litellm.BadRequestError(message="json_validate_failed", llm_provider="groq", model=LLM["model"])
        return type("Response", (), {"choices": [type("Choice", (), {
            "message": type("Message", (), {"content": strategy_json})(),
        })()]})()

    monkeypatch.setattr(agent.litellm, "acompletion", completion)
    strategy = await agent.synthesize("q", CLUSTER, SCORED, LLM)
    assert len(calls) == 2
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in calls[1]
    assert calls[1]["api_key"] == LLM["api_key"]
    assert strategy.generated_by == "llm" and strategy.fallback_reason is None


async def test_json_failure_after_retry_reports_real_reason(monkeypatch):
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        raise agent.litellm.BadRequestError(message="json_validate_failed", llm_provider="groq", model=LLM["model"])

    monkeypatch.setattr(agent.litellm, "acompletion", completion)
    strategy = await agent.synthesize("q", CLUSTER, SCORED, LLM)
    assert len(calls) == 2 and strategy.generated_by == "heuristic"
    assert "required JSON" in strategy.fallback_reason


async def test_non_json_provider_error_is_not_retried(monkeypatch):
    calls = []

    async def completion(**kwargs):
        calls.append(kwargs)
        raise agent.litellm.BadRequestError(message="model_not_found", llm_provider="groq", model=LLM["model"])

    monkeypatch.setattr(agent.litellm, "acompletion", completion)
    strategy = await agent.synthesize("q", CLUSTER, SCORED, LLM)
    assert len(calls) == 1 and strategy.generated_by == "heuristic"


async def test_workspace_key_passed_per_call_and_fenced_json_parsed(monkeypatch):
    seen: dict = {}
    body = (
        '{"title": "T", "thesis": "x", "value_proposition": "v", "target_audience": "a", "wedge": "w",'
        ' "execution_strategy": [], "go_to_market": [], "moat": "m", "risks": [], "kill_criteria": [],'
        ' "key_takeaways": []}'
    )

    class Msg:
        content = f"Here you go:\n```json\n{body}\n```"

    class Resp:
        choices = [type("C", (), {"message": Msg()})()]

    async def fake(**kwargs):
        seen.update(kwargs)
        return Resp()

    monkeypatch.setattr(agent.litellm, "acompletion", fake)
    strategy = await agent.synthesize("q", CLUSTER, SCORED, LLM)
    assert seen["api_key"] == "gsk_secret" and seen["model"] == LLM["model"]
    assert strategy.generated_by == "llm" and strategy.model == LLM["model"]
