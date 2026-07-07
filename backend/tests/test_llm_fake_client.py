import asyncio

import pytest
from pydantic import BaseModel

from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.fake_client import FakeLLMClient


class _Canned(BaseModel):
    value: str


def _run(coro):
    return asyncio.run(coro)


def test_mapping_form_returns_canned_response_per_query() -> None:
    spec_a = _Canned(value="a")
    spec_b = _Canned(value="b")
    client = FakeLLMClient({"query a": spec_a, "query b": spec_b})

    result_a = _run(
        client.get_structured(system="sys", user="query a", schema=_Canned, tool_name="emit")
    )
    result_b = _run(
        client.get_structured(system="sys", user="query b", schema=_Canned, tool_name="emit")
    )

    assert result_a is spec_a
    assert result_b is spec_b


def test_callable_form_is_invoked_with_call_kwargs() -> None:
    spec = _Canned(value="sunny")
    received: dict = {}

    def responder(*, system, user, schema, tool_name):
        received.update(system=system, user=user, schema=schema, tool_name=tool_name)
        return spec

    client = FakeLLMClient(responder)

    result = _run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name="emit_canned"
        )
    )

    assert result is spec
    assert received == {
        "system": "sys prompt",
        "user": "what's the weather",
        "schema": _Canned,
        "tool_name": "emit_canned",
    }


def test_mapping_form_raises_llm_error_on_demand() -> None:
    error = LLMError("transport failed", reason="timeout")
    client = FakeLLMClient({"query a": error})

    with pytest.raises(LLMError) as exc_info:
        _run(client.get_structured(system="sys", user="query a", schema=_Canned, tool_name="emit"))

    assert exc_info.value is error


def test_callable_form_raises_structured_output_error_on_demand() -> None:
    error = StructuredOutputError("could not validate", reason="validation_failed")
    client = FakeLLMClient(lambda **_: error)

    with pytest.raises(StructuredOutputError) as exc_info:
        _run(client.get_structured(system="sys", user="anything", schema=_Canned, tool_name="emit"))

    assert exc_info.value is error


def test_same_query_returns_identical_object_across_calls() -> None:
    spec = _Canned(value="sunny")
    client = FakeLLMClient({"query a": spec})

    first = _run(
        client.get_structured(system="sys", user="query a", schema=_Canned, tool_name="emit")
    )
    second = _run(
        client.get_structured(system="sys", user="query a", schema=_Canned, tool_name="emit")
    )

    assert first is spec
    assert second is spec


def test_unconfigured_query_raises_key_error() -> None:
    client = FakeLLMClient({"query a": _Canned(value="a")})

    with pytest.raises(KeyError):
        _run(
            client.get_structured(
                system="sys", user="unconfigured query", schema=_Canned, tool_name="emit"
            )
        )
