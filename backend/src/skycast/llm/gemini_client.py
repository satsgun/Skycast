"""google-genai-SDK-backed implementation of the LLMClient seam (Task 20.3).

The only module that imports google.genai. Structured output is obtained
via `response_mime_type="application/json"` + `response_schema=<schema>`
in GenerateContentConfig. response_schema is always a sanitized dict
built from `schema.model_json_schema()`, never the raw Pydantic class --
passing the class defers to the SDK's own conversion (google.genai.
_transformers.t_schema), which validates into types.Schema (extra=
"forbid", no field for e.g. `uniqueItems`) and raises on SkyCast's own
set[...]-typed fields. Since response_schema is always a dict,
response.parsed is never a validated instance either (the SDK only
populates it from a raw class), so message content is validated back
into `schema` by hand instead (the seam's contract is a validated
instance regardless).
"""

import re
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.usage import Usage

# gemini-3.5-flash has been observed twice to corrupt a token when
# generating structured JSON output: once as a stray control character
# replacing a non-ASCII character in a string field (silently passes
# schema validation -- see _find_control_character below), and once as
# a small int field corrupted into a runaway digit string, which trips
# Python's built-in guard against the CVE-2020-10735 int<->str
# conversion vulnerability instead of ever reaching validation. This is
# CPython's own stable error text for that guard, not a digit count
# (which is a configurable limit).
_MALFORMED_OUTPUT_SIGNATURE = "integer string conversion"

_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _find_control_character(value: Any, path: str = "") -> str | None:
    """Recursively scans a validated response for a stray control
    character (e.g. a NUL byte) in any string field -- a known
    gemini-3.5-flash corruption pattern (observed replacing "a with
    tilde" with \\x00) that passes schema validation cleanly, since a
    control character is still a syntactically valid str. Tab/newline/CR
    are excluded -- legitimate in synthesized answer text.
    """
    if isinstance(value, str):
        match = _CONTROL_CHAR_PATTERN.search(value)
        if match:
            return (
                f"field {path!r} contains a stray control character "
                f"(codepoint {ord(match.group())})"
            )
        return None
    if isinstance(value, dict):
        for key, sub in value.items():
            found = _find_control_character(sub, f"{path}.{key}" if path else str(key))
            if found:
                return found
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            found = _find_control_character(sub, f"{path}[{i}]")
            if found:
                return found
    return None


_UNSUPPORTED_SCHEMA_KEYWORDS = {
    "uniqueItems", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "patternProperties", "propertyNames", "unevaluatedProperties",
    "unevaluatedItems", "contains", "minContains", "maxContains", "prefixItems",
}


def _sanitize_schema(schema: Any) -> Any:
    """Strip JSON Schema keywords google-genai's types.Schema has no
    field for. Unlike OpenAI's sanitizer this needs no structural work
    (additionalProperties/required/default handling) -- google-genai's
    own schema-processing pipeline already does all of that; this is a
    blanket recursive key-strip only.
    """
    if isinstance(schema, dict):
        return {
            key: _sanitize_schema(value)
            for key, value in schema.items()
            if key not in _UNSUPPORTED_SCHEMA_KEYWORDS
        }
    if isinstance(schema, list):
        return [_sanitize_schema(item) for item in schema]
    return schema


class GeminiLLMClient(LLMClient):
    """Wraps the google-genai SDK behind the LLMClient seam.

    `model` and `api_key` are required, explicit values -- the caller
    sources them from config/env and passes them in (never ambient, and
    never logged). `client` is injectable for tests; when omitted, a real
    `genai.Client(api_key=api_key)` is constructed.

    `cache_enabled` (Task 23.6) is the A/B validation toggle. Like
    OpenAI, Gemini has no request-level opt-out for its implicit caching
    (per 23.4's own SDK check) -- so False here doesn't change the
    request at all, only `_record_usage`'s reporting, which then treats
    the call as if it were uncached.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        client: genai.Client | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self._model = model
        self._client = client if client is not None else genai.Client(api_key=api_key)
        self._cache_enabled = cache_enabled
        self.last_usage: Usage | None = None
        self.cumulative_usage: Usage | None = None

    async def get_structured(
        self, *, system: str, user: str, schema: type[BaseModel], tool_name: str
    ) -> BaseModel:
        config = self._build_config(schema=schema, system=system)

        response = await self._generate(contents=user, config=config)
        invocation_usage = self._record_usage(response)
        result, error_feedback = self._validate_response(response, schema=schema)
        if result is not None:
            self.last_usage = invocation_usage
            return result

        repair_contents = (
            f"{user}\n\nYour previous response was invalid: {error_feedback}. "
            "Respond again with corrected arguments."
        )
        repaired = await self._generate(contents=repair_contents, config=config)
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

    async def _generate(self, *, contents: str, config: types.GenerateContentConfig) -> Any:
        """The seam's contract is that only LLMError/StructuredOutputError
        cross it, so any exception (an APIError or otherwise) gets
        normalized here. Retries once, specifically on
        _MALFORMED_OUTPUT_SIGNATURE -- a known gemini-3.5-flash
        corruption pattern, not an ordinary transport failure -- before
        giving up and tagging the reason so it's identifiable as model
        output corruption rather than a real outage.
        """
        for attempt in range(2):
            try:
                return await self._client.aio.models.generate_content(
                    model=self._model, contents=contents, config=config
                )
            except Exception as exc:
                corrupted = _MALFORMED_OUTPUT_SIGNATURE in str(exc)
                if corrupted and attempt == 0:
                    continue
                reason = "malformed_model_output" if corrupted else type(exc).__name__
                message = (
                    f"gemini returned corrupted output: {exc}"
                    if corrupted
                    else f"gemini request failed: {exc}"
                )
                raise LLMError(message, reason=reason) from exc

    def _record_usage(self, response: Any) -> Usage:
        """Builds this call's Usage from the real response (Gemini's
        prompt_token_count/candidates_token_count naming maps to our
        input/output), folds it into the running self.cumulative_usage,
        and returns it so the caller can build the invocation-level
        total (summed across a repair retry, if one happens). Only
        called after a successful _generate() -- a call that raises
        never reaches here, so a failed call can't corrupt
        cumulative_usage.

        Prompt caching (Task 23.4) is implicit/automatic on Gemini's side,
        like OpenAI's -- no request-shape change, no cache-create step (the
        SDK's cached_content config field is for a separate explicit-caching
        flow this client doesn't use). cached_content_token_count is None
        when caching didn't engage (short prompt, or a model/response that
        doesn't support it) -- not an error. There's no write-count
        equivalent field at all, so cache_write_tokens stays at Usage's
        default of 0 for this vendor.

        response.usage_metadata.prompt_token_count is inclusive of cache
        activity on Gemini's side (unlike Anthropic's exclusive
        input_tokens), so input_tokens here is computed as the uncached
        remainder -- prompt_token_count minus whatever was read from
        cache (Task 23.7) -- keeping Usage.input_tokens meaning the same
        thing regardless of vendor.

        cache_enabled=False (Task 23.6) can't stop the server from
        caching, so it forces cache_read_tokens to 0 instead; with the
        subtrahend 0, input_tokens falls back to the raw
        prompt_token_count unchanged, correctly reporting the call as
        fully uncached.
        """
        cache_read_tokens = 0
        if self._cache_enabled:
            cache_read_tokens = response.usage_metadata.cached_content_token_count or 0
        usage = Usage(
            input_tokens=response.usage_metadata.prompt_token_count - cache_read_tokens,
            output_tokens=response.usage_metadata.candidates_token_count,
            model=self._model,
            cache_read_tokens=cache_read_tokens,
        )
        self.cumulative_usage = (
            usage if self.cumulative_usage is None else self.cumulative_usage + usage
        )
        return usage

    @staticmethod
    def _validate_response(
        response: Any, *, schema: type[BaseModel]
    ) -> tuple[BaseModel | None, str | None]:
        text = response.text
        if not text:
            return None, "empty response content"
        try:
            parsed = schema.model_validate_json(text)
        except ValidationError as exc:
            return None, str(exc)
        corrupted = _find_control_character(parsed.model_dump())
        if corrupted is not None:
            return None, corrupted
        return parsed, None

    @staticmethod
    def _build_config(*, schema: type[BaseModel], system: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_sanitize_schema(schema.model_json_schema()),
            system_instruction=system,
        )
