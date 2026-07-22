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

from typing import Any

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from skycast.llm.client import LLMClient
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.usage import Usage

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
    """

    def __init__(self, *, model: str, api_key: str, client: genai.Client | None = None) -> None:
        self._model = model
        self._client = client if client is not None else genai.Client(api_key=api_key)
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
        try:
            return await self._client.aio.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except errors.APIError as exc:
            raise LLMError(f"gemini request failed: {exc}", reason=type(exc).__name__) from exc
        except Exception as exc:
            # The seam's contract is that only LLMError/StructuredOutputError
            # cross it, so anything else gets normalized here too.
            raise LLMError(f"gemini request failed: {exc}", reason=type(exc).__name__) from exc

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
        """
        usage = Usage(
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
            model=self._model,
            cache_read_tokens=response.usage_metadata.cached_content_token_count or 0,
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
            return schema.model_validate_json(text), None
        except ValidationError as exc:
            return None, str(exc)

    @staticmethod
    def _build_config(*, schema: type[BaseModel], system: str) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_sanitize_schema(schema.model_json_schema()),
            system_instruction=system,
        )
