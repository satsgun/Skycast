import asyncio
import json

import httpx
import pytest
from openai import APIConnectionError, AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel

from skycast.llm.openai_client import OpenAILLMClient, _sanitize_schema
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.usage import Usage
from skycast.pipeline.data_needs import DataNeedsSpec
from skycast.pipeline.synthesis_output import SynthesisOutput

_TOOL_NAME = "emit_canned"


class _Canned(BaseModel):
    value: str


def _usage() -> CompletionUsage:
    return CompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)


def _chat_completion(*, content: str | None = None, refusal: str | None = None) -> ChatCompletion:
    message = ChatCompletionMessage(role="assistant", content=content, refusal=refusal)
    choice = Choice(finish_reason="stop", index=0, message=message)
    return ChatCompletion(
        id="chatcmpl_1", choices=[choice], created=1, model="gpt-5", object="chat.completion",
        usage=_usage(),
    )


def _valid_completion(data: dict) -> ChatCompletion:
    return _chat_completion(content=json.dumps(data))


def _invalid_completion() -> ChatCompletion:
    return _chat_completion(content=json.dumps({"wrong_field": "oops"}))


def _refusal_completion() -> ChatCompletion:
    return _chat_completion(refusal="I can't help with that.")


class _FakeCompletions:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeChat:
    def __init__(self, responses: list) -> None:
        self.completions = _FakeCompletions(responses)


def _build_client(responses: list) -> tuple[OpenAILLMClient, _FakeChat]:
    real = AsyncOpenAI(api_key="test-key")
    fake_chat = _FakeChat(responses)
    real.chat = fake_chat
    client = OpenAILLMClient(model="gpt-5", api_key="test-key", client=real)
    return client, fake_chat


def test_happy_path_returns_validated_schema_instance() -> None:
    client, fake_chat = _build_client([_valid_completion({"value": "sunny"})])

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake_chat.completions.calls) == 1
    call = fake_chat.completions.calls[0]
    assert call["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": _TOOL_NAME,
            "schema": _sanitize_schema(_Canned.model_json_schema()),
            "strict": True,
        },
    }
    assert call["messages"] == [
        {"role": "system", "content": "sys prompt"},
        {"role": "user", "content": "what's the weather"},
    ]


def test_repair_retry_succeeds_on_second_call() -> None:
    client, fake_chat = _build_client(
        [_invalid_completion(), _valid_completion({"value": "sunny"})]
    )

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake_chat.completions.calls) == 2


def test_repair_retry_exhausted_raises_structured_output_error() -> None:
    client, fake_chat = _build_client([_invalid_completion(), _invalid_completion()])

    with pytest.raises(StructuredOutputError):
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert len(fake_chat.completions.calls) == 2


def test_refusal_triggers_repair_then_recovers() -> None:
    client, fake_chat = _build_client(
        [_refusal_completion(), _valid_completion({"value": "sunny"})]
    )

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake_chat.completions.calls) == 2


def test_empty_content_triggers_repair_then_recovers() -> None:
    client, fake_chat = _build_client(
        [_chat_completion(), _valid_completion({"value": "sunny"})]
    )

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake_chat.completions.calls) == 2


def test_refusal_on_both_calls_raises_structured_output_error() -> None:
    client, fake_chat = _build_client([_refusal_completion(), _refusal_completion()])

    with pytest.raises(StructuredOutputError):
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert len(fake_chat.completions.calls) == 2


def test_transport_error_is_mapped_to_llm_error() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    transport_error = APIConnectionError(request=request)
    client, _ = _build_client([transport_error])

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert isinstance(exc_info.value.__cause__, OpenAIError)
    assert exc_info.value.__cause__ is transport_error


def test_constructing_without_client_builds_a_real_async_openai() -> None:
    client = OpenAILLMClient(model="gpt-5", api_key="test-key")

    assert isinstance(client._client, AsyncOpenAI)


@pytest.mark.parametrize(
    "raised",
    [
        RuntimeError("boom"),
        ValueError("bad value"),
        KeyError("missing"),
        OpenAIError("Missing credentials. Please pass an `api_key`..."),
    ],
)
def test_arbitrary_sdk_exceptions_are_mapped_to_llm_error(raised: Exception) -> None:
    client, _ = _build_client([raised])

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert exc_info.value.__cause__ is raised


def test_arbitrary_exception_during_repair_call_is_mapped_to_llm_error() -> None:
    raised = RuntimeError("boom during repair")
    client, fake_chat = _build_client([_invalid_completion(), raised])

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert exc_info.value.__cause__ is raised
    assert len(fake_chat.completions.calls) == 2


# --- Task 22.3: usage tracking ---


def _run_get_structured(client: OpenAILLMClient) -> BaseModel:
    return asyncio.run(
        client.get_structured(
            system="sys prompt", user="what's the weather", schema=_Canned, tool_name=_TOOL_NAME
        )
    )


def test_happy_path_sets_last_usage_and_cumulative_usage() -> None:
    client, _ = _build_client([_valid_completion({"value": "sunny"})])

    _run_get_structured(client)

    expected = Usage(input_tokens=10, output_tokens=5, model="gpt-5")
    assert client.last_usage == expected
    assert client.cumulative_usage == expected


def test_repair_retry_sums_both_calls_into_last_usage() -> None:
    client, _ = _build_client([_invalid_completion(), _valid_completion({"value": "sunny"})])

    _run_get_structured(client)

    expected = Usage(input_tokens=20, output_tokens=10, model="gpt-5")
    assert client.last_usage == expected
    assert client.cumulative_usage == expected


def test_repair_retry_exhausted_still_records_usage_before_raising() -> None:
    client, _ = _build_client([_invalid_completion(), _invalid_completion()])

    with pytest.raises(StructuredOutputError):
        _run_get_structured(client)

    expected = Usage(input_tokens=20, output_tokens=10, model="gpt-5")
    assert client.last_usage == expected
    assert client.cumulative_usage == expected


def test_cumulative_usage_accumulates_across_invocations_last_usage_does_not() -> None:
    client, _ = _build_client(
        [_valid_completion({"value": "sunny"}), _valid_completion({"value": "cloudy"})]
    )

    _run_get_structured(client)
    _run_get_structured(client)

    per_call = Usage(input_tokens=10, output_tokens=5, model="gpt-5")
    assert client.last_usage == per_call
    assert client.cumulative_usage == Usage(input_tokens=20, output_tokens=10, model="gpt-5")


def test_transport_error_on_first_ever_call_leaves_usage_none() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client, _ = _build_client([APIConnectionError(request=request)])

    with pytest.raises(LLMError):
        _run_get_structured(client)

    assert client.last_usage is None
    assert client.cumulative_usage is None


def test_transport_error_does_not_corrupt_prior_usage() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client, _ = _build_client(
        [_valid_completion({"value": "sunny"}), APIConnectionError(request=request)]
    )

    _run_get_structured(client)
    prior_last_usage = client.last_usage
    prior_cumulative_usage = client.cumulative_usage

    with pytest.raises(LLMError):
        _run_get_structured(client)

    assert client.last_usage == prior_last_usage
    assert client.cumulative_usage == prior_cumulative_usage


def test_exception_during_repair_call_records_first_calls_usage_but_not_last_usage() -> None:
    raised = RuntimeError("boom during repair")
    client, _ = _build_client([_invalid_completion(), raised])

    with pytest.raises(LLMError):
        _run_get_structured(client)

    # The first call genuinely succeeded and spent real tokens, so
    # cumulative_usage picks it up -- but this invocation never
    # produced a final answer, so last_usage isn't attributed to it.
    assert client.last_usage is None
    assert client.cumulative_usage == Usage(input_tokens=10, output_tokens=5, model="gpt-5")


# --- _sanitize_schema ---

_ALL_UNSUPPORTED_KEYWORDS = [
    "minLength", "maxLength", "pattern", "format",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "patternProperties", "unevaluatedProperties", "propertyNames",
    "minProperties", "maxProperties",
    "unevaluatedItems", "contains", "minContains", "maxContains",
    "minItems", "maxItems", "uniqueItems",
]


@pytest.mark.parametrize("keyword", _ALL_UNSUPPORTED_KEYWORDS)
def test_sanitize_schema_strips_each_unsupported_keyword(keyword: str) -> None:
    schema = {"type": "string", keyword: "irrelevant-value"}

    sanitized = _sanitize_schema(schema)

    assert keyword not in sanitized


def test_sanitize_schema_forces_additional_properties_false_and_full_required() -> None:
    schema = {
        "type": "object",
        "properties": {
            "a": {"type": "string"},
            "b": {"anyOf": [{"type": "integer"}, {"type": "null"}], "default": None},
        },
        "required": ["a"],
    }

    sanitized = _sanitize_schema(schema)

    assert sanitized["additionalProperties"] is False
    assert sanitized["required"] == ["a", "b"]
    assert "default" not in sanitized["properties"]["b"]


def test_sanitize_schema_recurses_into_defs() -> None:
    schema = {
        "$defs": {
            "Inner": {
                "type": "object",
                "properties": {"x": {"type": "integer", "minimum": 0}},
                "required": ["x"],
            }
        },
        "type": "object",
        "properties": {"inner": {"$ref": "#/$defs/Inner"}},
        "required": ["inner"],
    }

    sanitized = _sanitize_schema(schema)

    assert "minimum" not in sanitized["$defs"]["Inner"]["properties"]["x"]
    assert sanitized["$defs"]["Inner"]["additionalProperties"] is False


def _assert_openai_compatible(schema: dict) -> None:
    """Recursively assert `schema` contains none of OpenAI's unsupported
    keywords, and every object has additionalProperties:false plus a
    required list covering every property.
    """
    if not isinstance(schema, dict):
        return

    for keyword in _ALL_UNSUPPORTED_KEYWORDS:
        assert keyword not in schema, f"{keyword} present in {schema}"

    for defs_key in ("$defs", "definitions"):
        for value in schema.get(defs_key, {}).values():
            _assert_openai_compatible(value)

    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False
        properties = schema.get("properties", {})
        assert schema.get("required") == list(properties.keys())
        for value in properties.values():
            _assert_openai_compatible(value)

    items = schema.get("items")
    if isinstance(items, dict):
        _assert_openai_compatible(items)

    for union_key in ("anyOf", "oneOf", "allOf"):
        for variant in schema.get(union_key, []) or []:
            _assert_openai_compatible(variant)


def test_sanitized_data_needs_spec_schema_is_openai_compatible() -> None:
    _assert_openai_compatible(_sanitize_schema(DataNeedsSpec.model_json_schema()))


def test_sanitized_synthesis_output_schema_is_openai_compatible() -> None:
    _assert_openai_compatible(_sanitize_schema(SynthesisOutput.model_json_schema()))


def _assert_no_ref_with_siblings(schema: dict) -> None:
    if not isinstance(schema, dict):
        return
    if "$ref" in schema:
        assert len(schema) == 1, f"$ref has sibling keys, sanitizer doesn't unravel these: {schema}"
    for value in schema.values():
        if isinstance(value, dict):
            _assert_no_ref_with_siblings(value)
        elif isinstance(value, list):
            for item in value:
                _assert_no_ref_with_siblings(item)


def test_data_needs_spec_and_synthesis_output_never_use_ref_with_sibling_keys() -> None:
    _assert_no_ref_with_siblings(DataNeedsSpec.model_json_schema())
    _assert_no_ref_with_siblings(SynthesisOutput.model_json_schema())
