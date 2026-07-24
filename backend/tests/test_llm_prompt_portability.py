"""Prompt-portability check across LLM vendors (Task 20.5).

decompose()/synthesize() (pipeline/decompose.py, pipeline/
synthesize_stage.py) always call llm.get_structured() with the
module-level DECOMPOSE_SYSTEM_PROMPT/SYNTHESIZE_SYSTEM_PROMPT constants
(pipeline/prompts.py, Tasks 14.6/17.4) -- there is no vendor branch
anywhere in either stage function, and neither imports a vendor SDK.
Reading all three LLMClient implementations confirms none of them
inspects or transforms `system`'s content either: AnthropicLLMClient
passes it straight through as the `system` kwarg, OpenAILLMClient puts
it in the first message's `content`, GeminiLLMClient puts it in
`system_instruction` -- each treats it as a fully opaque string.

Finding: no vendor-specific prompt tweak was needed for either prompt.
Both stages succeed through all three real client classes with the
prompts completely unmodified (below). This is expected given the
prompts were authored to be pure reasoning-guidance text with no schema
restatement (the schema is supplied structurally per vendor -- tool use,
response_format, response_schema -- never in prose), so there's no
mechanism by which either prompt could have picked up a vendor
assumption. Live model-quality validation (does each vendor's model
produce *good* output for this prompt, not just schema-valid output) is
a separate question this offline suite can't answer -- see the opt-in,
env-gated live tests below, skipped by default (no API keys in CI), for
when a human wants to check that against real models.
"""

import asyncio
import os
from datetime import datetime, timezone

import pytest
from anthropic.types import Message, ToolUseBlock, Usage

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.gemini_client import GeminiLLMClient
from skycast.llm.openai_client import OpenAILLMClient
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.decompose import decompose
from skycast.pipeline.session_context import SessionContext
from skycast.pipeline.synthesize_stage import synthesize
from tests.test_llm_client_conformance import _AnthropicHarness, _GeminiHarness, _OpenAIHarness

_NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)
_QUERY = "what's the weather in Austin right now?"

_DECOMPOSE_TOOL_NAME = "emit_data_needs"
_SYNTHESIZE_TOOL_NAME = "emit_synthesis"

_DECOMPOSE_CANNED = {
    "location_names": ["Austin"],
    "granularities": ["CURRENT"],
    "variables": ["TEMPERATURE", "CONDITION"],
    "intent": "CONDITIONS",
}
_SYNTHESIZE_CANNED = {"text": "It's sunny and 28C in Austin right now.", "highlight": None}


def _anthropic_tool_use(tool_name: str, data: dict) -> Message:
    return Message(
        id="msg_1",
        content=[ToolUseBlock(id="tu_1", input=data, name=tool_name, type="tool_use")],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=Usage(input_tokens=10, output_tokens=5),
    )


def _forecast() -> Forecast:
    return Forecast(
        location=Location(id="test-austin", name="Austin", latitude=30.27, longitude=-97.74),
        units=Units(),
        current=HourlyReading(
            timestamp=_NOW, temperature=28.0, condition_code=ConditionCode.CLEAR
        ),
    )


# --- decompose() through each vendor, real prompt, unmodified ---


def test_decompose_succeeds_through_anthropic() -> None:
    client = _AnthropicHarness().build(
        [_anthropic_tool_use(_DECOMPOSE_TOOL_NAME, _DECOMPOSE_CANNED)]
    )

    result = asyncio.run(decompose(_QUERY, SessionContext(now=_NOW), client))

    assert isinstance(result, DataNeedsSpec)
    assert result.location_names == ["Austin"]
    assert result.intent == QueryIntent.CONDITIONS


def test_decompose_succeeds_through_openai() -> None:
    harness = _OpenAIHarness()
    client = harness.build([harness.valid_response(_DECOMPOSE_CANNED)])

    result = asyncio.run(decompose(_QUERY, SessionContext(now=_NOW), client))

    assert isinstance(result, DataNeedsSpec)
    assert result.location_names == ["Austin"]
    assert result.intent == QueryIntent.CONDITIONS


def test_decompose_succeeds_through_gemini() -> None:
    harness = _GeminiHarness()
    client = harness.build([harness.valid_response(_DECOMPOSE_CANNED)])

    result = asyncio.run(decompose(_QUERY, SessionContext(now=_NOW), client))

    assert isinstance(result, DataNeedsSpec)
    assert result.location_names == ["Austin"]
    assert result.intent == QueryIntent.CONDITIONS


# --- synthesize() through each vendor, real prompt, unmodified ---


def test_synthesize_succeeds_through_anthropic() -> None:
    client = _AnthropicHarness().build(
        [_anthropic_tool_use(_SYNTHESIZE_TOOL_NAME, _SYNTHESIZE_CANNED)]
    )

    result = asyncio.run(synthesize(_QUERY, [_forecast()], QueryIntent.CONDITIONS, client))

    assert result.text == _SYNTHESIZE_CANNED["text"]
    assert result.card.highlight is None


def test_synthesize_succeeds_through_openai() -> None:
    harness = _OpenAIHarness()
    client = harness.build([harness.valid_response(_SYNTHESIZE_CANNED)])

    result = asyncio.run(synthesize(_QUERY, [_forecast()], QueryIntent.CONDITIONS, client))

    assert result.text == _SYNTHESIZE_CANNED["text"]
    assert result.card.highlight is None


def test_synthesize_succeeds_through_gemini() -> None:
    harness = _GeminiHarness()
    client = harness.build([harness.valid_response(_SYNTHESIZE_CANNED)])

    result = asyncio.run(synthesize(_QUERY, [_forecast()], QueryIntent.CONDITIONS, client))

    assert result.text == _SYNTHESIZE_CANNED["text"]
    assert result.card.highlight is None


# --- opt-in live smoke tests, skipped by default (no API keys in CI) ---
# Mirrors tests/test_providers_open_meteo_provider.py's
# test_live_geocode_and_current_forecast_for_a_known_city.


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="opt-in live LLM test; set ANTHROPIC_API_KEY to run",
)
def test_live_decompose_through_anthropic() -> None:  # pragma: no cover
    client = AnthropicLLMClient(model=os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001"))

    result = asyncio.run(decompose(_QUERY, SessionContext(now=_NOW), client))

    assert isinstance(result, DataNeedsSpec)


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="opt-in live LLM test; set OPENAI_API_KEY to run",
)
def test_live_decompose_through_openai() -> None:  # pragma: no cover
    client = OpenAILLMClient(
        model=os.environ.get("LLM_MODEL", "gpt-5-mini"), api_key=os.environ["OPENAI_API_KEY"]
    )

    result = asyncio.run(decompose(_QUERY, SessionContext(now=_NOW), client))

    assert isinstance(result, DataNeedsSpec)


@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="opt-in live LLM test; set GEMINI_API_KEY to run",
)
def test_live_decompose_through_gemini() -> None:  # pragma: no cover
    client = GeminiLLMClient(
        model=os.environ.get("LLM_MODEL", "gemini-2.5-flash"), api_key=os.environ["GEMINI_API_KEY"]
    )

    result = asyncio.run(decompose(_QUERY, SessionContext(now=_NOW), client))

    assert isinstance(result, DataNeedsSpec)


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="opt-in live LLM test; set ANTHROPIC_API_KEY to run",
)
def test_live_synthesize_through_anthropic() -> None:  # pragma: no cover
    client = AnthropicLLMClient(model=os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001"))

    result = asyncio.run(synthesize(_QUERY, [_forecast()], QueryIntent.CONDITIONS, client))

    assert result.text


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="opt-in live LLM test; set OPENAI_API_KEY to run",
)
def test_live_synthesize_through_openai() -> None:  # pragma: no cover
    client = OpenAILLMClient(
        model=os.environ.get("LLM_MODEL", "gpt-5-mini"), api_key=os.environ["OPENAI_API_KEY"]
    )

    result = asyncio.run(synthesize(_QUERY, [_forecast()], QueryIntent.CONDITIONS, client))

    assert result.text


@pytest.mark.skipif(
    not os.environ.get("GEMINI_API_KEY"),
    reason="opt-in live LLM test; set GEMINI_API_KEY to run",
)
def test_live_synthesize_through_gemini() -> None:  # pragma: no cover
    client = GeminiLLMClient(
        model=os.environ.get("LLM_MODEL", "gemini-2.5-flash"), api_key=os.environ["GEMINI_API_KEY"]
    )

    result = asyncio.run(synthesize(_QUERY, [_forecast()], QueryIntent.CONDITIONS, client))

    assert result.text
