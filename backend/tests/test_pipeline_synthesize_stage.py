import asyncio
from datetime import date, datetime, timezone

import pytest

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import DailyReading, Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.fake_client import FakeLLMClient
from skycast.pipeline.data_needs import QueryIntent
from skycast.pipeline.prompts import SYNTHESIZE_SYSTEM_PROMPT
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.pipeline.synthesize_stage import render_forecast_lines, synthesize
from skycast.sse.payloads import ForecastBlock, Highlight, ReadingLocator


_QUERY = "Do I need an umbrella?"


def _run(coro):
    return asyncio.run(coro)


def _location(name: str = "Hyderabad") -> Location:
    return Location(
        id=f"in-memory:{name.lower()}", name=name,
        latitude=17.385, longitude=78.4867, timezone="Asia/Kolkata",
    )


def _current(temp: float = 27.0) -> HourlyReading:
    return HourlyReading(
        timestamp=datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc),
        temperature=temp,
        precip_probability=80.0,
        condition_code=ConditionCode.RAIN,
    )


def _forecast(
    name: str = "Hyderabad",
    *,
    current: HourlyReading | None = None,
    hourly: list[HourlyReading] | None = None,
    daily: list[DailyReading] | None = None,
) -> Forecast:
    if current is None and hourly is None and daily is None:
        current = _current()
    return Forecast(
        location=_location(name), units=Units(), current=current, hourly=hourly, daily=daily
    )


def _canned_output(highlight: Highlight | None = None) -> SynthesisOutput:
    return SynthesisOutput(text="Yes, bring an umbrella this evening.", highlight=highlight)


def test_happy_path_returns_text_and_card_and_calls_client_correctly() -> None:
    forecast = _forecast()
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    output = _canned_output(highlight)
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received.update(system=system, user=user, schema=schema, tool_name=tool_name)
        return output

    client = FakeLLMClient(responder)

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.text == output.text
    assert payload.card.forecasts == [forecast]
    assert payload.card.highlight == highlight
    assert received["system"] == SYNTHESIZE_SYSTEM_PROMPT
    assert received["schema"] is SynthesisOutput
    assert received["tool_name"] == "emit_synthesis"


def test_user_message_includes_intent_location_and_block_markers() -> None:
    forecast = _forecast(
        current=_current(),
        hourly=[_current(20.0)],
        daily=[DailyReading(date=date(2026, 7, 7), temp_min=18.0, temp_max=30.0, condition_code=ConditionCode.CLEAR)],
    )
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received["user"] = user
        return _canned_output()

    client = FakeLLMClient(responder)

    _run(synthesize("What's the weather like in Hyderabad?", [forecast], QueryIntent.CONDITIONS, client))

    user = received["user"]
    assert "Query: What's the weather like in Hyderabad?" in user
    assert "Intent: CONDITIONS" in user
    assert "Hyderabad" in user
    assert "current:" in user
    assert "hourly[0]:" in user
    assert "daily[0]:" in user


def test_user_message_differs_only_by_query_text() -> None:
    """Regression guard for the bug where synthesize() never received the
    original query, so the model had no way to know whether a DECISION
    question was about a jacket, an umbrella, or anything else -- two
    calls with identical forecasts/intent but different query text must
    produce user messages that differ (in the Query: line), proving the
    text is actually threaded through rather than silently dropped.
    """
    forecast = _forecast()
    captured: list[str] = []

    def responder(*, system, user, schema, tool_name):
        captured.append(user)
        return _canned_output()

    client = FakeLLMClient(responder)

    _run(synthesize("Should I wear a jacket?", [forecast], QueryIntent.DECISION, client))
    _run(synthesize("Do I need an umbrella?", [forecast], QueryIntent.DECISION, client))

    assert captured[0] != captured[1]
    assert "Query: Should I wear a jacket?" in captured[0]
    assert "Query: Do I need an umbrella?" in captured[1]


def test_card_carries_unmodified_input_forecast() -> None:
    forecast = _forecast()
    client = FakeLLMClient(lambda **_: _canned_output())

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.forecasts[0] == forecast


def test_no_highlight_from_llm_produces_no_highlight_card() -> None:
    client = FakeLLMClient(lambda **_: _canned_output(highlight=None))

    payload = _run(synthesize(_QUERY, [_forecast()], QueryIntent.DECISION, client))

    assert payload.card.highlight is None


def test_valid_current_highlight_passes_through() -> None:
    forecast = _forecast(current=_current())
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight == highlight


def test_valid_hourly_highlight_passes_through() -> None:
    forecast = _forecast(current=None, hourly=[_current(20.0), _current(22.0)])
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.HOURLY, index=1))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.OUTLOOK, client))

    assert payload.card.highlight == highlight


def test_valid_daily_highlight_passes_through() -> None:
    daily = [DailyReading(date=date(2026, 7, 7), temp_min=18.0, temp_max=30.0, condition_code=ConditionCode.CLEAR)]
    forecast = _forecast(current=None, daily=daily)
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.DAILY, index=0))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.OUTLOOK, client))

    assert payload.card.highlight == highlight


def test_out_of_range_forecast_index_drops_highlight() -> None:
    forecast = _forecast()
    highlight = Highlight(forecast_index=1, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight is None
    assert payload.text == _canned_output().text


def test_current_highlight_dropped_when_forecast_has_no_current() -> None:
    forecast = _forecast(current=None, hourly=[_current()])
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight is None


def test_hourly_highlight_dropped_when_forecast_has_no_hourly() -> None:
    forecast = _forecast(current=_current(), hourly=None)
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.HOURLY, index=0))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight is None


def test_hourly_highlight_dropped_when_index_beyond_series() -> None:
    forecast = _forecast(current=None, hourly=[_current()])
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.HOURLY, index=5))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight is None


def test_daily_highlight_dropped_when_forecast_has_no_daily() -> None:
    forecast = _forecast(current=_current(), daily=None)
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.DAILY, index=0))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight is None


def test_daily_highlight_dropped_when_index_beyond_series() -> None:
    daily = [DailyReading(date=date(2026, 7, 7), temp_min=18.0, temp_max=30.0, condition_code=ConditionCode.CLEAR)]
    forecast = _forecast(current=None, daily=daily)
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.DAILY, index=5))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    payload = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert payload.card.highlight is None


def test_comparison_two_forecasts_card_carries_both_and_highlight_points_into_second() -> None:
    austin = _forecast("Austin")
    dallas = _forecast("Dallas")
    highlight = Highlight(forecast_index=1, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    output = SynthesisOutput(text="Dallas is warmer.", highlight=highlight)
    client = FakeLLMClient(lambda **_: output)

    payload = _run(synthesize(_QUERY, [austin, dallas], QueryIntent.COMPARISON, client))

    assert payload.card.forecasts == [austin, dallas]
    assert payload.card.highlight.forecast_index == 1
    assert payload.card.forecasts[payload.card.highlight.forecast_index] == dallas
    assert payload.text == "Dallas is warmer."


def test_propagates_llm_error() -> None:
    error = LLMError("transport failed", reason="timeout")
    client = FakeLLMClient(lambda **_: error)

    with pytest.raises(LLMError) as exc_info:
        _run(synthesize(_QUERY, [_forecast()], QueryIntent.DECISION, client))

    assert exc_info.value is error


def test_propagates_structured_output_error() -> None:
    error = StructuredOutputError("could not validate", reason="validation_failed")
    client = FakeLLMClient(lambda **_: error)

    with pytest.raises(StructuredOutputError) as exc_info:
        _run(synthesize(_QUERY, [_forecast()], QueryIntent.DECISION, client))

    assert exc_info.value is error


def test_render_forecast_lines_matches_the_user_message_rendering() -> None:
    """render_forecast_lines is public so eval/harness/judge.py can reuse
    it to show the judge the same complete forecast data the model saw
    (single source of truth -- see judge.py's docstring). Confirms it
    produces exactly the lines _build_user_message embeds.
    """
    forecast = _forecast(
        current=_current(),
        hourly=[_current(20.0)],
        daily=[DailyReading(date=date(2026, 7, 7), temp_min=18.0, temp_max=30.0, condition_code=ConditionCode.CLEAR)],
    )
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received["user"] = user
        return _canned_output()

    client = FakeLLMClient(responder)
    _run(synthesize(_QUERY, [forecast], QueryIntent.CONDITIONS, client))

    lines = render_forecast_lines(0, forecast)

    assert "\n".join(lines) in received["user"]
    assert lines[0] == "Forecast 0: Hyderabad"


def test_determinism_same_inputs_and_fake_produce_equal_answer_payload() -> None:
    forecast = _forecast()
    highlight = Highlight(forecast_index=0, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    client = FakeLLMClient(lambda **_: _canned_output(highlight))

    first = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))
    second = _run(synthesize(_QUERY, [forecast], QueryIntent.DECISION, client))

    assert first == second
