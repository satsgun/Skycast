"""App-startup wiring: the real provider registry + real LLMClient
(Task 18.6). Assembles what Task 18.5's get_providers/get_llm_client
dependencies serve once the app's lifespan runs (see main.py) --
config/env driven, not hardcoded.
"""

import os

from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.client import LLMClient
from skycast.providers.base import WeatherProvider
from skycast.providers.in_memory import InMemoryProvider
from skycast.providers.open_meteo.provider import OpenMeteoProvider

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"


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
    """ANTHROPIC_MODEL from env, same default the record_*_fixtures.py
    scripts use. ANTHROPIC_API_KEY is read by the Anthropic SDK itself
    (AnthropicLLMClient's own convention, Task 14.3) -- never handled here.
    """
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)
    return AnthropicLLMClient(model=model)
