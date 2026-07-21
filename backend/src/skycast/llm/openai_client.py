"""OpenAI-SDK-backed implementation of the LLMClient seam (Task 20.2).

The only module that imports the openai SDK. Structured output is
obtained via Chat Completions' Structured Outputs: `schema.model_json_
schema()`, sanitized to fit OpenAI's strict-mode JSON Schema subset (see
_sanitize_schema), becomes the `response_format`'s json_schema. `.parse()`
is used for its finish-reason handling, but response_format is always
supplied as a pre-built dict (never the raw Pydantic class) -- passing
the class would let OpenAI's own schema conversion run instead of ours,
which does not strip the keywords its strict mode rejects, so `.parsed`
is never populated and `message.content` is validated back into `schema`
by hand instead (the seam's contract is a validated instance regardless).
"""

from typing import Any

import openai
from pydantic import BaseModel, ValidationError

from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.usage import Usage

_UNSUPPORTED_SCHEMA_KEYWORDS = {
    # strings
    "minLength", "maxLength", "pattern", "format",
    # numbers
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    # objects
    "patternProperties", "unevaluatedProperties", "propertyNames",
    "minProperties", "maxProperties",
    # arrays
    "unevaluatedItems", "contains", "minContains", "maxContains",
    "minItems", "maxItems", "uniqueItems",
}


def _sanitize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite a Pydantic `model_json_schema()` dict to fit OpenAI's
    Structured Outputs subset: strips validation keywords strict mode
    rejects (they constrain values, not structure -- this endpoint only
    accepts structure), forces `additionalProperties: false` and a full
    `required` list on every object (optionality is carried by nullable
    types instead of omission), and strips `default: null`. Builds new
    dicts rather than mutating in place. OpenAI-only dialect handling --
    the canonical Pydantic models this reads from are never altered.
    Every schema/subschema this recurses into is itself a dict, per JSON
    Schema's own shape -- no non-dict values are ever passed in.
    """
    sanitized = {k: v for k, v in schema.items() if k not in _UNSUPPORTED_SCHEMA_KEYWORDS}

    if sanitized.get("default", "unset") is None:
        sanitized.pop("default")

    for defs_key in ("$defs", "definitions"):
        defs = sanitized.get(defs_key)
        if isinstance(defs, dict):
            sanitized[defs_key] = {name: _sanitize_schema(value) for name, value in defs.items()}

    if sanitized.get("type") == "object":
        properties = sanitized.get("properties")
        if isinstance(properties, dict):
            sanitized["properties"] = {
                name: _sanitize_schema(value) for name, value in properties.items()
            }
            sanitized["required"] = list(sanitized["properties"].keys())
        sanitized["additionalProperties"] = False

    items = sanitized.get("items")
    if isinstance(items, dict):
        sanitized["items"] = _sanitize_schema(items)

    for union_key in ("anyOf", "oneOf", "allOf"):
        variants = sanitized.get(union_key)
        if isinstance(variants, list):
            sanitized[union_key] = [_sanitize_schema(variant) for variant in variants]

    return sanitized


class OpenAILLMClient(LLMClient):
    """Wraps the openai SDK behind the LLMClient seam.

    `model` and `api_key` are required, explicit values -- the caller
    sources them from config/env and passes them in (never ambient, and
    never logged). `client` is injectable for tests; when omitted, a real
    `openai.AsyncOpenAI(api_key=api_key)` is constructed.
    """

    def __init__(
        self, *, model: str, api_key: str, client: openai.AsyncOpenAI | None = None
    ) -> None:
        self._model = model
        self._client = client if client is not None else openai.AsyncOpenAI(api_key=api_key)
        self.last_usage: Usage | None = None
        self.cumulative_usage: Usage | None = None

    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        response_format = self._build_response_format(schema=schema, tool_name=tool_name)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        completion = await self._parse(messages=messages, response_format=response_format)
        invocation_usage = self._record_usage(completion)
        result, error_feedback = self._validate_response(completion, schema=schema)
        if result is not None:
            self.last_usage = invocation_usage
            return result

        repair_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"{user}\n\nYour previous response was invalid: {error_feedback}. "
                    "Respond again with corrected arguments."
                ),
            },
        ]
        repaired = await self._parse(messages=repair_messages, response_format=response_format)
        invocation_usage = invocation_usage + self._record_usage(repaired)
        result, error_feedback = self._validate_response(repaired, schema=schema)
        if result is not None:
            self.last_usage = invocation_usage
            return result

        self.last_usage = invocation_usage
        raise StructuredOutputError(
            f"model could not produce valid structured output for `{tool_name}` "
            "after one repair retry",
            reason="validation_failed",
        )

    async def _parse(
        self, *, messages: list[dict[str, Any]], response_format: dict[str, Any]
    ) -> Any:
        try:
            return await self._client.chat.completions.parse(
                model=self._model, messages=messages, response_format=response_format
            )
        except openai.OpenAIError as exc:
            raise LLMError(f"openai request failed: {exc}", reason=type(exc).__name__) from exc
        except Exception as exc:
            # The seam's contract is that only LLMError/StructuredOutputError
            # cross it, so anything else gets normalized here too.
            raise LLMError(f"openai request failed: {exc}", reason=type(exc).__name__) from exc

    def _record_usage(self, completion: Any) -> Usage:
        """Builds this call's Usage from the real response (OpenAI's
        prompt_tokens/completion_tokens naming maps to our input/output),
        folds it into the running self.cumulative_usage, and returns it
        so the caller can build the invocation-level total (summed
        across a repair retry, if one happens). Only called after a
        successful _parse() -- a call that raises never reaches here, so
        a failed call can't corrupt cumulative_usage.
        """
        usage = Usage(
            input_tokens=completion.usage.prompt_tokens,
            output_tokens=completion.usage.completion_tokens,
            model=self._model,
        )
        self.cumulative_usage = (
            usage if self.cumulative_usage is None else self.cumulative_usage + usage
        )
        return usage

    @staticmethod
    def _validate_response(
        completion: Any, *, schema: type[BaseModel]
    ) -> tuple[BaseModel | None, str | None]:
        message = completion.choices[0].message
        if message.refusal:
            return None, f"model refused: {message.refusal}"
        if not message.content:
            return None, "empty response content"
        try:
            return schema.model_validate_json(message.content), None
        except ValidationError as exc:
            return None, str(exc)

    @staticmethod
    def _build_response_format(*, schema: type[BaseModel], tool_name: str) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": tool_name,
                "schema": _sanitize_schema(schema.model_json_schema()),
                "strict": True,
            },
        }
