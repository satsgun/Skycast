import asyncio
import json

import pytest
from google.genai import errors, types

# _transformers is a private google-genai module. Importing it here is a
# deliberate choice: it's the only way to actually run our sanitized
# schema through the SDK's real ref-inlining/validation pipeline (see
# test_sanitized_*_is_accepted_by_gemini below) rather than just
# asserting our own output structurally. If google-genai restructures
# this module, this test file needs updating.
from google.genai import _transformers
from pydantic import BaseModel

from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.gemini_client import GeminiLLMClient, _sanitize_schema
from skycast.pipeline.data_needs import DataNeedsSpec
from skycast.pipeline.synthesis_output import SynthesisOutput

_TOOL_NAME = "emit_canned"


class _Canned(BaseModel):
    value: str


def _response(text: str | None) -> types.GenerateContentResponse:
    if text is None:
        return types.GenerateContentResponse(candidates=[])
    part = types.Part(text=text)
    content = types.Content(parts=[part], role="model")
    candidate = types.Candidate(content=content, finish_reason="STOP")
    return types.GenerateContentResponse(candidates=[candidate])


def _valid_response(data: dict) -> types.GenerateContentResponse:
    return _response(json.dumps(data))


def _invalid_response() -> types.GenerateContentResponse:
    return _response(json.dumps({"wrong_field": "oops"}))


def _empty_response() -> types.GenerateContentResponse:
    return _response(None)


class _FakeModels:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeAio:
    def __init__(self, responses: list) -> None:
        self.models = _FakeModels(responses)


class _FakeGeminiClient:
    def __init__(self, responses: list) -> None:
        self.aio = _FakeAio(responses)


def _build_client(responses: list) -> tuple[GeminiLLMClient, _FakeGeminiClient]:
    fake = _FakeGeminiClient(responses)
    client = GeminiLLMClient(model="gemini-2.5-flash", api_key="test-key", client=fake)
    return client, fake


def test_happy_path_returns_validated_schema_instance() -> None:
    client, fake = _build_client([_valid_response({"value": "sunny"})])

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake.aio.models.calls) == 1
    call = fake.aio.models.calls[0]
    assert call["model"] == "gemini-2.5-flash"
    assert call["contents"] == "query"
    config = call["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema == _sanitize_schema(_Canned.model_json_schema())
    assert config.system_instruction == "sys prompt"


def test_repair_retry_succeeds_on_second_call() -> None:
    client, fake = _build_client([_invalid_response(), _valid_response({"value": "sunny"})])

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake.aio.models.calls) == 2


def test_repair_retry_exhausted_raises_structured_output_error() -> None:
    client, fake = _build_client([_invalid_response(), _invalid_response()])

    with pytest.raises(StructuredOutputError):
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert len(fake.aio.models.calls) == 2


def test_empty_content_triggers_repair_then_recovers() -> None:
    client, fake = _build_client([_empty_response(), _valid_response({"value": "sunny"})])

    result = asyncio.run(
        client.get_structured(
            system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
        )
    )

    assert result == _Canned(value="sunny")
    assert len(fake.aio.models.calls) == 2


def test_transport_error_is_mapped_to_llm_error() -> None:
    transport_error = errors.APIError(500, {"error": {"message": "boom", "status": "INTERNAL"}})
    client, _ = _build_client([transport_error])

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert isinstance(exc_info.value.__cause__, errors.APIError)
    assert exc_info.value.__cause__ is transport_error


def test_constructing_without_client_builds_a_real_genai_client() -> None:
    from google import genai

    client = GeminiLLMClient(model="gemini-2.5-flash", api_key="test-key")

    assert isinstance(client._client, genai.Client)


@pytest.mark.parametrize(
    "raised",
    [RuntimeError("boom"), ValueError("bad value"), KeyError("missing")],
)
def test_arbitrary_sdk_exceptions_are_mapped_to_llm_error(raised: Exception) -> None:
    client, _ = _build_client([raised])

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert exc_info.value.__cause__ is raised


def test_arbitrary_exception_during_repair_call_is_mapped_to_llm_error() -> None:
    raised = RuntimeError("boom during repair")
    client, fake = _build_client([_invalid_response(), raised])

    with pytest.raises(LLMError) as exc_info:
        asyncio.run(
            client.get_structured(
                system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
            )
        )

    assert exc_info.value.__cause__ is raised
    assert len(fake.aio.models.calls) == 2


# --- _sanitize_schema ---

_UNSUPPORTED_KEYWORDS = [
    "uniqueItems", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "patternProperties", "propertyNames", "unevaluatedProperties",
    "unevaluatedItems", "contains", "minContains", "maxContains", "prefixItems",
]


@pytest.mark.parametrize("keyword", _UNSUPPORTED_KEYWORDS)
def test_sanitize_schema_strips_each_unsupported_keyword(keyword: str) -> None:
    schema = {"type": "array", "items": {"type": "string"}, keyword: "irrelevant-value"}

    sanitized = _sanitize_schema(schema)

    assert keyword not in sanitized


def test_sanitize_schema_leaves_supported_keywords_untouched() -> None:
    schema = {
        "type": "string",
        "minLength": 1,
        "minimum": 0,
        "format": "date-time",
        "default": None,
    }

    sanitized = _sanitize_schema(schema)

    assert sanitized == schema


def test_sanitize_schema_recurses_into_defs_and_lists() -> None:
    schema = {
        "$defs": {
            "Inner": {
                "type": "array",
                "items": {"type": "string"},
                "uniqueItems": True,
            }
        },
        "anyOf": [{"$ref": "#/$defs/Inner"}, {"type": "null"}],
    }

    sanitized = _sanitize_schema(schema)

    assert "uniqueItems" not in sanitized["$defs"]["Inner"]
    assert "uniqueItems" not in sanitized["anyOf"][0]


def test_sanitized_data_needs_spec_schema_is_accepted_by_gemini() -> None:
    sanitized = _sanitize_schema(DataNeedsSpec.model_json_schema())

    result = _transformers.t_schema(None, sanitized)

    assert isinstance(result, types.Schema)


def test_sanitized_synthesis_output_schema_is_accepted_by_gemini() -> None:
    sanitized = _sanitize_schema(SynthesisOutput.model_json_schema())

    result = _transformers.t_schema(None, sanitized)

    assert isinstance(result, types.Schema)


def _assert_no_additional_properties(schema) -> None:
    if isinstance(schema, dict):
        assert "additionalProperties" not in schema
        assert "additional_properties" not in schema
        for value in schema.values():
            _assert_no_additional_properties(value)
    elif isinstance(schema, list):
        for item in schema:
            _assert_no_additional_properties(item)


def test_data_needs_spec_and_synthesis_output_never_set_additional_properties() -> None:
    """Gemini's Developer API (non-Vertex) mode rejects any schema
    containing additionalProperties -- none of our models set
    ConfigDict(extra="forbid"), the only thing that would emit it, so
    there's nothing to strip. This guards that assumption instead of
    defensively stripping a key that can't appear today.
    """
    _assert_no_additional_properties(DataNeedsSpec.model_json_schema())
    _assert_no_additional_properties(SynthesisOutput.model_json_schema())
