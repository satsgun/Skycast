import asyncio
from datetime import datetime, timezone

import pytest

from skycast.domain.location import Location
from skycast.domain.provider import Granularity, TimeWindow, WeatherVariable
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.fake_client import FakeLLMClient
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.decompose import decompose
from skycast.pipeline.prompts import DECOMPOSE_SYSTEM_PROMPT
from skycast.pipeline.relative_time import RelativeTimeKind, RelativeTimeSpec
from skycast.pipeline.session_context import SessionContext

_QUERY = "do I need an umbrella this evening?"


def _run(coro):
    return asyncio.run(coro)


def _now() -> datetime:
    return datetime(2026, 7, 7, 18, 0, tzinfo=timezone.utc)


def _minimal_ctx() -> SessionContext:
    return SessionContext(now=_now())


def _full_ctx() -> SessionContext:
    return SessionContext(
        now=_now(),
        default_location=Location(
            id="in-memory:hyderabad-in",
            name="Hyderabad",
            latitude=17.385,
            longitude=78.4867,
            timezone="Asia/Kolkata",
        ),
        units_hint="celsius",
        carried_location_name="Springfield",
        carried_window=TimeWindow(
            start=datetime(2026, 7, 6, 18, 0, tzinfo=timezone.utc),
            end=datetime(2026, 7, 6, 22, 0, tzinfo=timezone.utc),
        ),
    )


def _canned_spec() -> DataNeedsSpec:
    return DataNeedsSpec(
        location_names=[],
        granularities={Granularity.HOURLY},
        time=RelativeTimeSpec(kind=RelativeTimeKind.THIS_EVENING),
        variables={WeatherVariable.PRECIP_PROBABILITY},
        intent=QueryIntent.DECISION,
    )


def test_happy_path_returns_the_canned_spec_and_calls_client_correctly() -> None:
    spec = _canned_spec()
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received.update(system=system, user=user, schema=schema, tool_name=tool_name)
        return spec

    client = FakeLLMClient(responder)

    result = _run(decompose(_QUERY, _minimal_ctx(), client))

    assert result is spec
    assert received["system"] == DECOMPOSE_SYSTEM_PROMPT
    assert received["schema"] is DataNeedsSpec
    assert received["tool_name"] == "emit_data_needs"


def test_user_message_includes_full_session_context() -> None:
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received["user"] = user
        return _canned_spec()

    client = FakeLLMClient(responder)
    ctx = _full_ctx()

    _run(decompose(_QUERY, ctx, client))

    user = received["user"]
    assert _QUERY in user
    assert ctx.now.isoformat() in user
    assert "Hyderabad" in user
    assert "Asia/Kolkata" in user
    assert "celsius" in user
    assert "Springfield" in user
    assert ctx.carried_window.start.isoformat() in user
    assert ctx.carried_window.end.isoformat() in user


def test_user_message_omits_optional_sections_when_context_is_minimal() -> None:
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received["user"] = user
        return _canned_spec()

    client = FakeLLMClient(responder)
    ctx = _minimal_ctx()

    _run(decompose(_QUERY, ctx, client))

    user = received["user"]
    assert _QUERY in user
    assert ctx.now.isoformat() in user
    assert "Default location" not in user
    assert "Units hint" not in user
    assert "Carried location" not in user
    assert "Carried time window" not in user


def test_propagates_llm_error() -> None:
    error = LLMError("transport failed", reason="timeout")
    client = FakeLLMClient(lambda **_: error)

    with pytest.raises(LLMError) as exc_info:
        _run(decompose(_QUERY, _minimal_ctx(), client))

    assert exc_info.value is error


def test_propagates_structured_output_error() -> None:
    error = StructuredOutputError("could not validate", reason="validation_failed")
    client = FakeLLMClient(lambda **_: error)

    with pytest.raises(StructuredOutputError) as exc_info:
        _run(decompose(_QUERY, _minimal_ctx(), client))

    assert exc_info.value is error


def test_determinism_same_query_and_context_and_fake_returns_identical_spec() -> None:
    spec = _canned_spec()
    client = FakeLLMClient(lambda **_: spec)
    ctx = _minimal_ctx()

    first = _run(decompose(_QUERY, ctx, client))
    second = _run(decompose(_QUERY, ctx, client))

    assert first is spec
    assert second is spec
