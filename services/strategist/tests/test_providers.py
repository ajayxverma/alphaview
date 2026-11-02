import pytest

from alphaview_common.netguard import UnsafeEndpointError
from alphaview_strategist.providers import PROVIDERS, call_kwargs

FAMOUS = {"openai", "anthropic", "gemini", "groq", "mistral", "deepseek", "xai", "cohere",
          "perplexity", "together", "fireworks", "openrouter", "azure", "ollama", "openai_compatible"}


def test_catalog_covers_major_providers():
    assert FAMOUS <= set(PROVIDERS)
    for p in PROVIDERS.values():
        assert p.prefix.endswith("/")
        assert p.docs_url.startswith("https://")


async def test_groq_kwargs():
    kw = await call_kwargs(PROVIDERS["groq"], "llama-3.3-70b-versatile", {"api_key": "k"}, {}, False)
    assert kw == {"model": "groq/llama-3.3-70b-versatile", "api_key": "k"}


async def test_azure_requires_public_https_endpoint():
    spec = PROVIDERS["azure"]
    kw = await call_kwargs(spec, "my-deploy", {"api_key": "k"}, {"api_base": "https://8.8.8.8/", "api_version": "2024-10-21"}, False)
    assert kw["api_base"] == "https://8.8.8.8" and kw["api_version"] == "2024-10-21"
    with pytest.raises(UnsafeEndpointError):
        await call_kwargs(spec, "d", {"api_key": "k"}, {"api_base": "https://10.1.2.3"}, False)


async def test_ollama_needs_private_opt_in():
    spec = PROVIDERS["ollama"]
    with pytest.raises(UnsafeEndpointError):
        await call_kwargs(spec, "llama3.1", {}, {"api_base": "http://host.docker.internal:11434"}, False)
    kw = await call_kwargs(spec, "llama3.1", {}, {"api_base": "http://host.docker.internal:11434"}, True)
    assert kw["model"] == "ollama/llama3.1" and "api_key" not in kw


async def test_openai_compatible_placeholder_key():
    kw = await call_kwargs(PROVIDERS["openai_compatible"], "m", {}, {"api_base": "https://8.8.8.8/v1"}, False)
    assert kw["api_key"] == "not-needed"
