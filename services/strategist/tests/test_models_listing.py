import httpx
import pytest

from alphaview_strategist.providers import PROVIDERS, list_models


def client_returning(payload, status: int = 200, seen: dict | None = None) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen["url"] = str(request.url)
            seen["headers"] = dict(request.headers)
        return httpx.Response(status, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_groq_lists_chat_models_and_filters_audio():
    seen: dict = {}
    payload = {"data": [
        {"id": "openai/gpt-oss-120b", "active": True},
        {"id": "llama-3.1-8b-instant", "active": True},
        {"id": "whisper-large-v3", "active": True},
        {"id": "meta-llama/llama-guard-4-12b", "active": True},
        {"id": "retired-model", "active": False},
    ]}
    async with client_returning(payload, seen=seen) as client:
        models = await list_models(client, PROVIDERS["groq"], {"api_key": "gsk_x"}, {}, False)
    assert models[0] == "llama-3.1-8b-instant"  # suggested models first
    assert set(models) == {"llama-3.1-8b-instant", "openai/gpt-oss-120b"}
    assert seen["headers"]["authorization"] == "Bearer gsk_x"


async def test_gemini_filters_by_generate_content_and_strips_prefix():
    payload = {"models": [
        {"name": "models/gemini-2.0-flash", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
    ]}
    seen: dict = {}
    async with client_returning(payload, seen=seen) as client:
        models = await list_models(client, PROVIDERS["gemini"], {"api_key": "AIza"}, {}, False)
    assert models == ["gemini-2.0-flash"]
    assert "key=AIza" in seen["url"]


async def test_anthropic_headers():
    seen: dict = {}
    async with client_returning({"data": [{"id": "claude-x"}]}, seen=seen) as client:
        await list_models(client, PROVIDERS["anthropic"], {"api_key": "sk-ant"}, {}, False)
    assert seen["headers"]["x-api-key"] == "sk-ant"
    assert "anthropic-version" in seen["headers"]


async def test_rejected_key():
    async with client_returning({"error": "bad"}, status=401) as client:
        with pytest.raises(PermissionError):
            await list_models(client, PROVIDERS["openai"], {"api_key": "bad"}, {}, False)


async def test_static_fallback_for_unlistable_provider():
    async with client_returning({}) as client:
        assert await list_models(client, PROVIDERS["perplexity"], {"api_key": "k"}, {}, False) == ["sonar", "sonar-pro"]


async def test_self_hosted_requires_base_url():
    async with client_returning({}) as client:
        with pytest.raises(ValueError):
            await list_models(client, PROVIDERS["ollama"], {}, {}, True)
