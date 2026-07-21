"""Shared conformance suite for every LLMClient implementation (Task 20.1).

Parametrized over one harness per vendor client: AnthropicLLMClient,
OpenAILLMClient, and GeminiLLMClient. The test bodies below never change
per vendor, since they only ever go through the Harness protocol, never
a vendor SDK type directly. This is what actually proves "three
implementations of one interface" rather than leaving it an unverified
claim.
"""

import asyncio
import json
import logging
from typing import Any, Protocol

import httpx
import pytest
from anthropic import APIConnectionError as AnthropicAPIConnectionError
from anthropic.types import Message, ToolUseBlock, Usage
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from openai import APIConnectionError as OpenAIAPIConnectionError
from openai import AsyncOpenAI, OpenAIError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice
from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel

from skycast.llm.anthropic_client import AnthropicLLMClient
from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.gemini_client import GeminiLLMClient
from skycast.llm.openai_client import OpenAILLMClient

_TOOL_NAME = "emit_canned"


class _Canned(BaseModel):
    value: str


class Harness(Protocol):
    def build(self, responses: list) -> LLMClient: ...

    def build_with_credential(
        self, monkeypatch: pytest.MonkeyPatch, secret: str, responses: list
    ) -> LLMClient: ...

    def valid_response(self, data: dict) -> object: ...

    def invalid_response(self) -> object: ...

    def transport_error(self) -> Exception: ...

    def unexpected_error(self) -> Exception: ...

    def missing_credentials_error(self) -> Exception: ...

    def call_count(self, client: LLMClient) -> int: ...


class _FakeMessages:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeAnthropicClient:
    def __init__(self, responses: list) -> None:
        self.messages = _FakeMessages(responses)


def _usage() -> Usage:
    return Usage(input_tokens=10, output_tokens=5)


def _tool_use_message(data: dict) -> Message:
    return Message(
        id="msg_1",
        content=[ToolUseBlock(id="tu_1", input=data, name=_TOOL_NAME, type="tool_use")],
        model="claude-haiku-4-5-20251001",
        role="assistant",
        stop_reason="tool_use",
        stop_sequence=None,
        type="message",
        usage=_usage(),
    )


class _AnthropicHarness:
    def build(self, responses: list) -> LLMClient:
        fake = _FakeAnthropicClient(responses)
        return AnthropicLLMClient(model="claude-haiku-4-5-20251001", client=fake)

    def build_with_credential(
        self, monkeypatch: pytest.MonkeyPatch, secret: str, responses: list
    ) -> LLMClient:
        monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
        client = AnthropicLLMClient(model="claude-haiku-4-5-20251001")
        client._client.messages = _FakeMessages(responses)
        return client

    def valid_response(self, data: dict) -> object:
        return _tool_use_message(data)

    def invalid_response(self) -> object:
        return _tool_use_message({"wrong_field": "oops"})

    def transport_error(self) -> Exception:
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        return AnthropicAPIConnectionError(request=request)

    def unexpected_error(self) -> Exception:
        return RuntimeError("boom")

    def missing_credentials_error(self) -> Exception:
        return TypeError(
            "Could not resolve authentication method. Expected one of "
            "api_key, auth_token, or credentials to be set."
        )

    def call_count(self, client: LLMClient) -> int:
        return len(client._client.messages.calls)


class _FakeCompletions:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeChat:
    def __init__(self, responses: list) -> None:
        self.completions = _FakeCompletions(responses)


def _chat_completion(data: dict) -> ChatCompletion:
    message = ChatCompletionMessage(role="assistant", content=json.dumps(data))
    choice = Choice(finish_reason="stop", index=0, message=message)
    return ChatCompletion(
        id="chatcmpl_1", choices=[choice], created=1, model="gpt-5", object="chat.completion",
        usage=CompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


class _OpenAIHarness:
    def build(self, responses: list) -> LLMClient:
        real = AsyncOpenAI(api_key="test-key")
        real.chat = _FakeChat(responses)
        return OpenAILLMClient(model="gpt-5", api_key="test-key", client=real)

    def build_with_credential(
        self, monkeypatch: pytest.MonkeyPatch, secret: str, responses: list
    ) -> LLMClient:
        # OpenAILLMClient takes api_key explicitly (not ambient, unlike
        # Anthropic's env-var convention), so no env var is needed here --
        # `monkeypatch` is accepted only to satisfy the Harness protocol.
        real = AsyncOpenAI(api_key=secret)
        real.chat = _FakeChat(responses)
        return OpenAILLMClient(model="gpt-5", api_key=secret, client=real)

    def valid_response(self, data: dict) -> object:
        return _chat_completion(data)

    def invalid_response(self) -> object:
        return _chat_completion({"wrong_field": "oops"})

    def transport_error(self) -> Exception:
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        return OpenAIAPIConnectionError(request=request)

    def unexpected_error(self) -> Exception:
        return RuntimeError("boom")

    def missing_credentials_error(self) -> Exception:
        return OpenAIError(
            "Missing credentials. Please pass an `api_key`, `workload_identity`, "
            "`admin_api_key`, or set the `OPENAI_API_KEY` or `OPENAI_ADMIN_KEY` "
            "environment variable."
        )

    def call_count(self, client: LLMClient) -> int:
        return len(client._client.chat.completions.calls)


class _FakeGeminiModels:
    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class _FakeGeminiAio:
    def __init__(self, responses: list) -> None:
        self.models = _FakeGeminiModels(responses)


class _FakeGeminiClient:
    def __init__(self, responses: list) -> None:
        self.aio = _FakeGeminiAio(responses)


def _gemini_response(data: dict) -> genai_types.GenerateContentResponse:
    part = genai_types.Part(text=json.dumps(data))
    content = genai_types.Content(parts=[part], role="model")
    candidate = genai_types.Candidate(content=content, finish_reason="STOP")
    return genai_types.GenerateContentResponse(candidates=[candidate])


class _GeminiHarness:
    def build(self, responses: list) -> LLMClient:
        fake = _FakeGeminiClient(responses)
        return GeminiLLMClient(model="gemini-2.5-flash", api_key="test-key", client=fake)

    def build_with_credential(
        self, monkeypatch: pytest.MonkeyPatch, secret: str, responses: list
    ) -> LLMClient:
        # GeminiLLMClient takes api_key explicitly (not ambient), so no
        # env var is needed here -- `monkeypatch` is accepted only to
        # satisfy the Harness protocol.
        fake = _FakeGeminiClient(responses)
        return GeminiLLMClient(model="gemini-2.5-flash", api_key=secret, client=fake)

    def valid_response(self, data: dict) -> object:
        return _gemini_response(data)

    def invalid_response(self) -> object:
        return _gemini_response({"wrong_field": "oops"})

    def transport_error(self) -> Exception:
        return genai_errors.APIError(500, {"error": {"message": "boom", "status": "INTERNAL"}})

    def unexpected_error(self) -> Exception:
        return RuntimeError("boom")

    def missing_credentials_error(self) -> Exception:
        return genai_errors.ClientError(
            401, {"error": {"message": "API key not valid", "status": "UNAUTHENTICATED"}}
        )

    def call_count(self, client: LLMClient) -> int:
        return len(client._client.aio.models.calls)


_HARNESSES: list[Harness] = [_AnthropicHarness(), _OpenAIHarness(), _GeminiHarness()]


@pytest.fixture(params=_HARNESSES, ids=lambda h: type(h).__name__)
def harness(request: pytest.FixtureRequest) -> Harness:
    return request.param


def _get_structured(client: LLMClient) -> BaseModel:
    return asyncio.run(
        client.get_structured(
            system="sys prompt", user="query", schema=_Canned, tool_name=_TOOL_NAME
        )
    )


def test_get_structured_returns_validated_schema_instance(harness: Harness) -> None:
    client = harness.build([harness.valid_response({"value": "sunny"})])

    result = _get_structured(client)

    assert result == _Canned(value="sunny")


def test_repair_retry_recovers_on_second_call(harness: Harness) -> None:
    client = harness.build(
        [harness.invalid_response(), harness.valid_response({"value": "sunny"})]
    )

    result = _get_structured(client)

    assert result == _Canned(value="sunny")
    assert harness.call_count(client) == 2


def test_repair_retry_exhausted_raises_structured_output_error_only(
    harness: Harness,
) -> None:
    client = harness.build([harness.invalid_response(), harness.invalid_response()])

    with pytest.raises(StructuredOutputError) as exc_info:
        _get_structured(client)

    assert type(exc_info.value) is StructuredOutputError


def test_transport_error_maps_to_llm_error_only(harness: Harness) -> None:
    client = harness.build([harness.transport_error()])

    with pytest.raises(LLMError) as exc_info:
        _get_structured(client)

    assert type(exc_info.value) is LLMError


def test_unexpected_exception_maps_to_llm_error_only(harness: Harness) -> None:
    client = harness.build([harness.unexpected_error()])

    with pytest.raises(LLMError) as exc_info:
        _get_structured(client)

    assert type(exc_info.value) is LLMError


def test_missing_credentials_maps_to_llm_error_not_raw(harness: Harness) -> None:
    client = harness.build([harness.missing_credentials_error()])

    with pytest.raises(LLMError) as exc_info:
        _get_structured(client)

    assert type(exc_info.value) is LLMError


def test_never_logs_credential_happy_path(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "sk-canary-secret-must-never-be-logged"
    client = harness.build_with_credential(
        monkeypatch, secret, [harness.valid_response({"value": "sunny"})]
    )
    caplog.set_level(logging.DEBUG)

    _get_structured(client)

    assert all(secret not in record.getMessage() for record in caplog.records)


def test_never_logs_credential_on_error_path(
    harness: Harness, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "sk-canary-secret-must-never-be-logged"
    client = harness.build_with_credential(monkeypatch, secret, [harness.transport_error()])
    caplog.set_level(logging.DEBUG)

    with pytest.raises(LLMError) as exc_info:
        _get_structured(client)

    assert all(secret not in record.getMessage() for record in caplog.records)
    assert secret not in str(exc_info.value)
