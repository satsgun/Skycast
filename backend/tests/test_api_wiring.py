from skycast.api.wiring import build_llm_client, build_provider_registry
from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.providers.in_memory import InMemoryProvider


def test_build_provider_registry_returns_in_memory_entry() -> None:
    registry = build_provider_registry()

    assert set(registry) == {"in-memory"}
    assert isinstance(registry["in-memory"], InMemoryProvider)


def test_build_llm_client_returns_anthropic_client() -> None:
    client = build_llm_client()

    assert isinstance(client, AnthropicLLMClient)


def test_build_llm_client_uses_default_model_when_env_unset(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)

    client = build_llm_client()

    assert client._model == "claude-haiku-4-5-20251001"


def test_build_llm_client_respects_anthropic_model_env_var(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    client = build_llm_client()

    assert client._model == "claude-opus-4-8"
