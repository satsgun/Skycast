"""App-startup wiring: the real provider registry + real LLMClient
(Task 18.6). Assembles what Task 18.5's get_providers/get_llm_client
dependencies serve once the app's lifespan runs (see main.py) --
config/env driven, not hardcoded.
"""

import os

from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.client import LLMClient
from skycast.llm.gemini_client import GeminiLLMClient
from skycast.llm.openai_client import OpenAILLMClient
from skycast.providers.base import WeatherProvider
from skycast.providers.in_memory import InMemoryProvider
from skycast.providers.open_meteo.provider import OpenMeteoProvider

_DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-5-mini",
    "gemini": "gemini-2.5-flash",
}


def build_provider_registry() -> dict[str, WeatherProvider]:
    """The real (v1) dict[str, WeatherProvider] plan()/execute() expect
    (Tasks 15.3/16.2). OpenMeteoProvider is listed first -- select_provider's
    v1 ranking (provider_selection.py) is order-preserving, so insertion
    order is what actually decides which provider serves a request when
    (as today) multiple providers report the same capabilities.
    InMemoryProvider stays registered too (harmless, currently
    unreachable via selection given the trivial v1 ranking).
    """
    return {"open-meteo": OpenMeteoProvider(), "in-memory": InMemoryProvider()}


def build_llm_client() -> LLMClient:
    """LLM_VENDOR selects exactly one client, chosen once at process
    startup (Task 20.4) -- no routing. Defaults to "anthropic" when
    unset, preserving Task 18.6's original zero-config behavior.
    LLM_MODEL is generic (not per-vendor-named) since only one vendor is
    ever active in a process; falls back to a per-vendor default when
    unset. ANTHROPIC_API_KEY is never read here -- the anthropic SDK
    reads it ambiently inside AsyncAnthropic() (Task 14.3, unchanged).
    OPENAI_API_KEY/GEMINI_API_KEY are read via os.environ[...] (not
    .get()) so a missing key fails loudly here with a KeyError naming
    the exact missing var, rather than falling through to the vendor
    SDK's own generic ambient-credential error.
    """
    vendor = os.environ.get("LLM_VENDOR", "anthropic")

    if vendor == "anthropic":
        model = os.environ.get("LLM_MODEL", _DEFAULT_MODELS["anthropic"])
        return AnthropicLLMClient(model=model)
    if vendor == "openai":
        model = os.environ.get("LLM_MODEL", _DEFAULT_MODELS["openai"])
        return OpenAILLMClient(model=model, api_key=os.environ["OPENAI_API_KEY"])
    if vendor == "gemini":
        model = os.environ.get("LLM_MODEL", _DEFAULT_MODELS["gemini"])
        return GeminiLLMClient(model=model, api_key=os.environ["GEMINI_API_KEY"])

    raise ValueError(
        f"unknown LLM_VENDOR: {vendor!r} -- expected 'anthropic', 'openai', or 'gemini'"
    )
