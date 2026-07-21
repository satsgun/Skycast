"""Anthropic-SDK-backed implementation of the LLMClient seam (Task 14.3).

The only module that imports the Anthropic SDK. Structured output is
obtained via Anthropic tool use: schema.model_json_schema() (pydantic's
own exporter) becomes the tool's input_schema, tool_choice forces that
exact tool, and the returned tool_use block's `input` is validated back
into `schema`.
"""

from typing import Any, Literal

import anthropic
from pydantic import BaseModel, ValidationError

from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.usage import Usage

_DEFAULT_MAX_TOKENS = 1024


class AnthropicLLMClient(LLMClient):
    """Wraps the anthropic SDK behind the LLMClient seam.

    `model` is a required, explicit string (e.g. "claude-...") -- the
    caller sources it from config/env; this class never hard-codes one.
    `client` is injectable for tests (mocked transport); when omitted, a
    real `anthropic.AsyncAnthropic()` is constructed (reads
    ANTHROPIC_API_KEY from env, the SDK's own convention).

    `cache_ttl` (Task 23.2) is, like `model`, an explicit constructor
    value the caller sources from config/env -- this class never reads
    os.environ itself. It marks the system prompt and tool-schema blocks
    (identical on every call to a given stage) as cacheable via
    Anthropic's prompt caching; the per-call user message is never
    cached, since it varies every call.
    """

    def __init__(
        self,
        *,
        model: str,
        client: anthropic.AsyncAnthropic | None = None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        cache_ttl: Literal["5m", "1h"] = "5m",
    ) -> None:
        self._model = model
        self._client = client if client is not None else anthropic.AsyncAnthropic()
        self._max_tokens = max_tokens
        self._cache_ttl = cache_ttl
        self.last_usage: Usage | None = None
        self.cumulative_usage: Usage | None = None

    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        tool = self._build_tool(schema=schema, tool_name=tool_name)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]

        message = await self._create(system=system, messages=messages, tool=tool, tool_name=tool_name)
        invocation_usage = self._record_usage(message)
        result, error_feedback = self._validate_response(message, schema=schema, tool_name=tool_name)
        if result is not None:
            self.last_usage = invocation_usage
            return result

        repair_messages = [
            {
                "role": "user",
                "content": (
                    f"{user}\n\nYour previous call to `{tool_name}` was invalid: "
                    f"{error_feedback}. Call `{tool_name}` again with corrected arguments."
                ),
            }
        ]
        repaired = await self._create(
            system=system, messages=repair_messages, tool=tool, tool_name=tool_name
        )
        invocation_usage = invocation_usage + self._record_usage(repaired)
        result, error_feedback = self._validate_response(repaired, schema=schema, tool_name=tool_name)
        if result is not None:
            self.last_usage = invocation_usage
            return result

        self.last_usage = invocation_usage
        raise StructuredOutputError(
            f"model could not produce valid `{tool_name}` arguments after one repair retry",
            reason="validation_failed",
        )

    async def _create(
        self, *, system: str, messages: list[dict[str, Any]], tool: dict[str, Any], tool_name: str
    ) -> Any:
        try:
            return await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral", "ttl": self._cache_ttl},
                    }
                ],
                messages=messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
            )
        except anthropic.AnthropicError as exc:
            raise LLMError(f"anthropic request failed: {exc}", reason=type(exc).__name__) from exc
        except Exception as exc:
            # The SDK can raise outside its own AnthropicError hierarchy --
            # e.g. a plain TypeError from auth-method resolution during
            # header validation when no API key is configured. The seam's
            # contract is that only LLMError/StructuredOutputError cross
            # it, so anything else gets normalized here too. str(exc) is
            # the SDK's own message; never add request headers or the API
            # key to it.
            raise LLMError(f"anthropic request failed: {exc}", reason=type(exc).__name__) from exc

    def _record_usage(self, message: Any) -> Usage:
        """Builds this call's Usage from the real response, folds it into
        the running self.cumulative_usage, and returns it so the caller
        can build the invocation-level total (summed across a repair
        retry, if one happens). Only called after a successful _create()
        -- a call that raises never reaches here, so a failed call can't
        corrupt cumulative_usage.
        """
        usage = Usage(
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
            model=self._model,
            cache_write_tokens=message.usage.cache_creation_input_tokens or 0,
            cache_read_tokens=message.usage.cache_read_input_tokens or 0,
        )
        self.cumulative_usage = (
            usage if self.cumulative_usage is None else self.cumulative_usage + usage
        )
        return usage

    def _build_tool(self, *, schema: type[BaseModel], tool_name: str) -> dict[str, Any]:
        return {
            "name": tool_name,
            "description": schema.__doc__ or tool_name,
            "input_schema": schema.model_json_schema(),
            "cache_control": {"type": "ephemeral", "ttl": self._cache_ttl},
        }

    @staticmethod
    def _validate_response(
        message: Any, *, schema: type[BaseModel], tool_name: str
    ) -> tuple[BaseModel | None, str | None]:
        for block in message.content:
            if block.type == "tool_use" and block.name == tool_name:
                try:
                    return schema.model_validate(block.input), None
                except ValidationError as exc:
                    return None, str(exc)
        return None, f"no `{tool_name}` tool_use block in response"
