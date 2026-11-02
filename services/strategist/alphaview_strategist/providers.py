"""Catalog of supported LLM providers and how to turn stored credentials into LiteLLM call kwargs."""

import re
from dataclasses import dataclass, field

import httpx
from pydantic import BaseModel

from alphaview_common.netguard import validate_endpoint


class FieldSpec(BaseModel):
    key: str
    label: str
    secret: bool = False
    required: bool = True
    help: str | None = None


API_KEY = FieldSpec(key="api_key", label="API key", secret=True)


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    prefix: str
    default_model: str
    models: tuple[str, ...]
    docs_url: str
    credential_fields: tuple[FieldSpec, ...] = (API_KEY,)
    config_fields: tuple[FieldSpec, ...] = field(default_factory=tuple)
    # Placeholder key for OpenAI-compatible servers that do not check keys.
    key_placeholder: str | None = None


_PROVIDERS: list[ProviderSpec] = [
    ProviderSpec("openai", "OpenAI", "openai/", "gpt-4o-mini",
                 ("gpt-4o-mini", "gpt-4o", "gpt-4.1", "gpt-4.1-mini", "o3-mini"),
                 "https://platform.openai.com/api-keys"),
    ProviderSpec("anthropic", "Anthropic (Claude)", "anthropic/", "claude-3-5-sonnet-latest",
                 ("claude-3-5-sonnet-latest", "claude-3-7-sonnet-latest", "claude-3-5-haiku-latest"),
                 "https://console.anthropic.com/settings/keys"),
    ProviderSpec("gemini", "Google Gemini", "gemini/", "gemini-2.0-flash",
                 ("gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"),
                 "https://aistudio.google.com/app/apikey"),
    ProviderSpec("groq", "Groq", "groq/", "llama-3.3-70b-versatile",
                 ("llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"),
                 "https://console.groq.com/keys"),
    ProviderSpec("mistral", "Mistral AI", "mistral/", "mistral-large-latest",
                 ("mistral-large-latest", "mistral-small-latest", "open-mistral-nemo"),
                 "https://console.mistral.ai/api-keys"),
    ProviderSpec("deepseek", "DeepSeek", "deepseek/", "deepseek-chat",
                 ("deepseek-chat", "deepseek-reasoner"),
                 "https://platform.deepseek.com/api_keys"),
    ProviderSpec("xai", "xAI (Grok)", "xai/", "grok-2-latest",
                 ("grok-2-latest", "grok-beta"),
                 "https://console.x.ai"),
    ProviderSpec("cohere", "Cohere", "cohere_chat/", "command-r-plus",
                 ("command-r-plus", "command-r"),
                 "https://dashboard.cohere.com/api-keys"),
    ProviderSpec("perplexity", "Perplexity", "perplexity/", "sonar",
                 ("sonar", "sonar-pro"),
                 "https://www.perplexity.ai/settings/api"),
    ProviderSpec("together", "Together AI", "together_ai/", "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                 ("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct-Turbo",
                  "deepseek-ai/DeepSeek-V3"),
                 "https://api.together.ai/settings/api-keys"),
    ProviderSpec("fireworks", "Fireworks AI", "fireworks_ai/", "accounts/fireworks/models/llama-v3p3-70b-instruct",
                 ("accounts/fireworks/models/llama-v3p3-70b-instruct",
                  "accounts/fireworks/models/deepseek-v3"),
                 "https://fireworks.ai/account/api-keys"),
    ProviderSpec("openrouter", "OpenRouter", "openrouter/", "openai/gpt-4o-mini",
                 ("openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "meta-llama/llama-3.3-70b-instruct",
                  "google/gemini-2.0-flash-001"),
                 "https://openrouter.ai/keys"),
    ProviderSpec("azure", "Azure OpenAI", "azure/", "",
                 (),
                 "https://portal.azure.com",
                 config_fields=(
                     FieldSpec(key="api_base", label="Endpoint", help="https://<resource>.openai.azure.com"),
                     FieldSpec(key="api_version", label="API version", help="e.g. 2024-10-21"),
                 )),
    ProviderSpec("ollama", "Ollama (self-hosted)", "ollama/", "llama3.1",
                 ("llama3.1", "qwen2.5", "mistral"),
                 "https://ollama.com",
                 credential_fields=(),
                 config_fields=(
                     FieldSpec(key="api_base", label="Server URL", help="e.g. http://host.docker.internal:11434"),
                 )),
    ProviderSpec("openai_compatible", "OpenAI-compatible (vLLM, LM Studio, LiteLLM proxy...)", "openai/", "",
                 (),
                 "https://docs.litellm.ai/docs/providers/openai_compatible",
                 credential_fields=(FieldSpec(key="api_key", label="API key", secret=True, required=False),),
                 config_fields=(FieldSpec(key="api_base", label="Base URL", help="e.g. https://my-llm.example.com/v1"),),
                 key_placeholder="not-needed"),
]

PROVIDERS: dict[str, ProviderSpec] = {p.id: p for p in _PROVIDERS}

# How to list the models a key can use: (url, auth style). Relative URLs are appended to the user's api_base.
MODEL_LISTING: dict[str, tuple[str, str]] = {
    "openai": ("https://api.openai.com/v1/models", "bearer"),
    "anthropic": ("https://api.anthropic.com/v1/models?limit=1000", "anthropic"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000", "query"),
    "groq": ("https://api.groq.com/openai/v1/models", "bearer"),
    "mistral": ("https://api.mistral.ai/v1/models", "bearer"),
    "deepseek": ("https://api.deepseek.com/models", "bearer"),
    "xai": ("https://api.x.ai/v1/models", "bearer"),
    "cohere": ("https://api.cohere.com/v1/models?endpoint=chat&page_size=1000", "bearer"),
    "together": ("https://api.together.xyz/v1/models", "bearer"),
    "fireworks": ("https://api.fireworks.ai/inference/v1/models", "bearer"),
    "openrouter": ("https://openrouter.ai/api/v1/models", "none"),
    "ollama": ("/api/tags", "none"),
    "openai_compatible": ("/models", "bearer"),
}

# Model ids that are not chat/text-generation models (speech, embeddings, safety, images...).
_NON_CHAT = re.compile(
    r"whisper|tts|embed|moderation|dall-e|guard|transcri|rerank|image|audio|realtime|playai|orpheus", re.I
)


def _extract_ids(provider: str, payload: object) -> list[str]:
    items = payload if isinstance(payload, list) else (
        (payload.get("data") or payload.get("models") or []) if isinstance(payload, dict) else []
    )
    ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        if provider == "gemini" and "generateContent" not in item.get("supportedGenerationMethods", []):
            continue
        if provider == "together" and item.get("type") not in (None, "chat", "language"):
            continue
        if item.get("active") is False:
            continue
        model_id = str(item.get("id") or item.get("name") or "")
        if provider == "gemini":
            model_id = model_id.removeprefix("models/")
        if model_id and not _NON_CHAT.search(model_id):
            ids.append(model_id)
    return ids


async def list_models(
    client: httpx.AsyncClient, spec: ProviderSpec, creds: dict, config: dict, allow_private: bool
) -> list[str]:
    """Models available to these credentials, suggested ones first. Falls back to the static list."""
    listing = MODEL_LISTING.get(spec.id)
    if listing is None:
        return list(spec.models)
    url, auth = listing
    if url.startswith("/"):
        if not config.get("api_base"):
            raise ValueError("Enter the server URL first")
        url = (await validate_endpoint(config["api_base"], allow_private)) + url

    key = creds.get("api_key", "")
    headers: dict[str, str] = {}
    params: dict[str, str] = {}
    if auth == "bearer" and key:
        headers["Authorization"] = f"Bearer {key}"
    elif auth == "anthropic":
        headers.update({"x-api-key": key, "anthropic-version": "2023-06-01"})
    elif auth == "query":
        params["key"] = key

    resp = await client.get(url, headers=headers, params=params, timeout=20)
    if resp.status_code in (401, 403):
        raise PermissionError("The provider rejected this API key")
    resp.raise_for_status()

    found = set(_extract_ids(spec.id, resp.json()))
    preferred = [m for m in spec.models if m in found]
    return preferred + sorted(found - set(preferred))[:500]


async def call_kwargs(spec: ProviderSpec, model: str, creds: dict, config: dict, allow_private: bool) -> dict:
    """LiteLLM kwargs for one call. Keys are passed per call, never via process env."""
    kwargs: dict = {"model": f"{spec.prefix}{model}"}
    if creds.get("api_key"):
        kwargs["api_key"] = creds["api_key"]
    elif spec.key_placeholder:
        kwargs["api_key"] = spec.key_placeholder
    if config.get("api_base"):
        kwargs["api_base"] = await validate_endpoint(config["api_base"], allow_private)
    if config.get("api_version"):
        kwargs["api_version"] = config["api_version"]
    return kwargs
