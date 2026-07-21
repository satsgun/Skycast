import asyncio

import httpx
import pytest
from anthropic import AnthropicError, APIConnectionError, AsyncAnthropic
from anthropic.types import Message, TextBlock, ToolUseBlock, Usage
from pydantic import BaseModel

from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.usage import Usage as SkycastUsage

_TOOL_NAME = "emit_canned"


class _Canned(BaseModel):
    value: str


def _usage() -> Usage:
    return Usage(input_tokens=10, output_tokens=5)


def _tool_use_message(input: dict, name: str = _TOOL_NAME) -> Message:
    return Message(
        id="msg_1",
        content=[ToolUseBlock(id="tu_1", input=input, name=name, type="tool_use")],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=_usage(),
    )


def _text_only_message() -> Message:
    return Message(
        id="msg_1",
        content=[TextBlock(text="sorry, I can't do that", type="text")],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="end_turn",
        stop_sequence=None,
        type="message",
        usage=_usage(),
    )


class _FakeMessages:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeAnthropicClient:
    def __init__(self, responses: list) -> None:
        self.messages = _FakeMessages(responses)


def test_happy_path_returns_validated_schema_instance() -> None:
    fake = _FakeAnthropicClient([_tool_use_message({"value": "sunny"})])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake.messages.calls) == 1
    call = fake.messages.calls[0]
    assert call["tools"] == [
        {
            "name": _TOOL_NAME,
            "description": _Canned.__doc__ or _TOOL_NAME,
            "input_schema": _Canned.model_json_schema(),
        }
    ]
    assert call["tool_choice"] == {"type": "tool", "name": _TOOL_NAME}
    assert call["system"] == "sys prompt"


def test_repair_retry_succeeds_on_second_call() -> None:
    fake = _FakeAnthropicClient(
        [
            _tool_use_message({"wrong_field": "oops"}),
            _tool_use_message({"value": "sunny"}),
        ]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake.messages.calls) == 2


def test_repair_retry_exhausted_raises_structured_output_error() -> None:
    fake = _FakeAnthropicClient(
        [
            _tool_use_message({"wrong_field": "oops"}),
            _tool_use_message({"wrong_field": "still wrong"}),
        ]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(StructuredOutputError):
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert len(fake.messages.calls) == 2


def test_no_tool_use_block_triggers_repair_then_recovers() -> None:
    fake = _FakeAnthropicClient(
        [
            _text_only_message(),
            _tool_use_message({"value": "sunny"}),
        ]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake.messages.calls) == 2


def test_no_tool_use_block_on_both_calls_raises_structured_output_error() -> None:
    fake = _FakeAnthropicClient([_text_only_message(), _text_only_message()])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(StructuredOutputError):
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert len(fake.messages.calls) == 2


def test_transport_error_is_mapped_to_llm_error() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake = _FakeAnthropicClient([APIConnectionError(request=request)])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert isinstance(exc_info.value.__cause__, AnthropicError)


def test_constructing_without_client_builds_a_real_async_anthropic() -> None:
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001")

    assert isinstance(client._client, AsyncAnthropic)


@pytest.mark.parametrize(
    "raised",
    [
        TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        ),
        RuntimeError("boom"),
        ValueError("bad value"),
        KeyError("missing"),
    ],
)
def test_arbitrary_sdk_exceptions_are_mapped_to_llm_error(raised: Exception) -> None:
    fake = _FakeAnthropicClient([raised])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert exc_info.value.__cause__ is raised


def test_arbitrary_exception_during_repair_call_is_mapped_to_llm_error() -> None:
    raised = RuntimeError("boom during repair")
    fake = _FakeAnthropicClient([_tool_use_message({"wrong_field": "oops"}), raised])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert exc_info.value.__cause__ is raised
    assert len(fake.messages.calls) == 2


# --- Task 22.2: usage tracking ---


def _run_get_structured(client: AnthropicLLMClient) -> BaseModel:
    return asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )


def test_happy_path_sets_last_usage_and_cumulative_usage() -> None:
    fake = _FakeAnthropicClient([_tool_use_message({"value": "sunny"})])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    _run_get_structured(client)

    expected = SkycastUsage(input_tokens=10, output_tokens=5, model="claude-haiku-4-5-20251001")
    assert client.last_usage == expected
    assert client.cumulative_usage == expected


def test_repair_retry_sums_both_calls_into_last_usage() -> None:
    fake = _FakeAnthropicClient(
        [
            _tool_use_message({"wrong_field": "oops"}),
            _tool_use_message({"value": "sunny"}),
        ]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    _run_get_structured(client)

    expected = SkycastUsage(input_tokens=20, output_tokens=10, model="claude-haiku-4-5-20251001")
    assert client.last_usage == expected
    assert client.cumulative_usage == expected


def test_repair_retry_exhausted_still_records_usage_before_raising() -> None:
    fake = _FakeAnthropicClient(
        [
            _tool_use_message({"wrong_field": "oops"}),
            _tool_use_message({"wrong_field": "still wrong"}),
        ]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(StructuredOutputError):
        _run_get_structured(client)

    expected = SkycastUsage(input_tokens=20, output_tokens=10, model="claude-haiku-4-5-20251001")
    assert client.last_usage == expected
    assert client.cumulative_usage == expected


def test_cumulative_usage_accumulates_across_invocations_last_usage_does_not() -> None:
    fake = _FakeAnthropicClient(
        [_tool_use_message({"value": "sunny"}), _tool_use_message({"value": "cloudy"})]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    _run_get_structured(client)
    _run_get_structured(client)

    per_call = SkycastUsage(input_tokens=10, output_tokens=5, model="claude-haiku-4-5-20251001")
    assert client.last_usage == per_call
    assert client.cumulative_usage == SkycastUsage(
        input_tokens=20, output_tokens=10, model="claude-haiku-4-5-20251001"
    )


def test_transport_error_on_first_ever_call_leaves_usage_none() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake = _FakeAnthropicClient([APIConnectionError(request=request)])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(LLMError):
        _run_get_structured(client)

    assert client.last_usage is None
    assert client.cumulative_usage is None


def test_transport_error_does_not_corrupt_prior_usage() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    fake = _FakeAnthropicClient(
        [_tool_use_message({"value": "sunny"}), APIConnectionError(request=request)]
    )
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    _run_get_structured(client)
    prior_last_usage = client.last_usage
    prior_cumulative_usage = client.cumulative_usage

    with pytest.raises(LLMError):
        _run_get_structured(client)

    assert client.last_usage == prior_last_usage
    assert client.cumulative_usage == prior_cumulative_usage


def test_exception_during_repair_call_records_first_calls_usage_but_not_last_usage() -> None:
    raised = RuntimeError("boom during repair")
    fake = _FakeAnthropicClient([_tool_use_message({"wrong_field": "oops"}), raised])
    client = AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    with pytest.raises(LLMError):
        _run_get_structured(client)

    # The first call genuinely succeeded and spent real tokens, so
    # cumulative_usage picks it up -- but this invocation never
    # produced a final answer, so last_usage isn't attributed to it.
    assert client.last_usage is None
    assert client.cumulative_usage == SkycastUsage(
        input_tokens=10, output_tokens=5, model="claude-haiku-4-5-20251001"
    )
