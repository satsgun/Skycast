import pytest

from skycast.api.wiring import build_cors_origins, build_llm_client, build_provider_registry
from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.gemini_client import GeminiLLMClient
from skycast.llm.openai_client import OpenAILLMClient
from skycast.providers.in_memory import InMemoryProvider
from skycast.providers.open_meteo.provider import OpenMeteoProvider


def test_build_cors_origins_defaults_to_localhost_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)

    assert build_cors_origins() == ["http://localhost:5173"]


def test_build_cors_origins_strips_trailing_slash(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://skycast-pi-jet.vercel.app/")

    assert build_cors_origins() == ["https://skycast-pi-jet.vercel.app"]


def test_build_cors_origins_leaves_no_trailing_slash_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://skycast-pi-jet.vercel.app")

    assert build_cors_origins() == ["https://skycast-pi-jet.vercel.app"]


def test_build_provider_registry_returns_open_meteo_and_in_memory() -> None:
    registry = build_provider_registry()

    # Order is load-bearing: select_provider's v1 ranking is
    # order-preserving, so insertion order decides which provider
    # actually serves a request when both report the same capabilities.
    assert list(registry) == ["open-meteo", "in-memory"]
    assert isinstance(registry["open-meteo"], OpenMeteoProvider)
    assert isinstance(registry["in-memory"], InMemoryProvider)


def test_build_llm_client_defaults_to_anthropic_when_vendor_unset(monkeypatch) -> None:
    monkeypatch.delenv("LLM_VENDOR", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)

    client = build_llm_client()

    assert isinstance(client, AnthropicLLMClient)
    assert client._model == "claude-haiku-4-5-20251001"


def test_build_llm_client_respects_llm_model_env_var_for_anthropic(monkeypatch) -> None:
    monkeypatch.delenv("LLM_VENDOR", raising=False)
    monkeypatch.setenv("LLM_MODEL", "claude-opus-4-8")

    client = build_llm_client()

    assert client._model == "claude-opus-4-8"


def test_build_llm_client_selects_openai_when_vendor_is_openai(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    client = build_llm_client()

    assert isinstance(client, OpenAILLMClient)
    assert client._model == "gpt-5-mini"
    assert client._client.api_key == "test-key"


def test_build_llm_client_respects_llm_model_env_var_for_openai(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-5")

    client = build_llm_client()

    assert client._model == "gpt-5"


def test_build_llm_client_raises_when_openai_api_key_missing(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(KeyError, match="OPENAI_API_KEY"):
        build_llm_client()


def test_build_llm_client_selects_gemini_when_vendor_is_gemini(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    client = build_llm_client()

    assert isinstance(client, GeminiLLMClient)
    assert client._model == "gemini-2.5-flash"
    # google-genai exposes no public api_key accessor on Client; reaching
    # into the private BaseApiClient is the only way to confirm the key
    # was actually threaded through (same tolerance test_llm_gemini_
    # client.py already takes with google.genai._transformers).
    assert client._client._api_client.api_key == "test-key"


def test_build_llm_client_respects_llm_model_env_var_for_gemini(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "gemini-2.5-pro")

    client = build_llm_client()

    assert client._model == "gemini-2.5-pro"


def test_build_llm_client_raises_when_gemini_api_key_missing(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "gemini")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(KeyError, match="GEMINI_API_KEY"):
        build_llm_client()


def test_build_llm_client_raises_value_error_on_unknown_vendor(monkeypatch) -> None:
    monkeypatch.setenv("LLM_VENDOR", "mistral")

    with pytest.raises(ValueError, match="mistral"):
        build_llm_client()
