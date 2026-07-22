"""Usage: per-call LLM token usage (Task 22.1).

Not part of the LLMClient interface -- get_structured() still returns
only the validated schema instance. A client MAY set self.last_usage /
self.cumulative_usage as instance state after each call (see
LLMClient's docstring for the informal contract); this is the shape
those attributes carry when it does.
"""

from pydantic import BaseModel, ConfigDict, Field


class Usage(BaseModel):
    """Token usage for one (or one accumulated set of) LLM call(s).

    model is optional -- set when the caller wants to attribute cost to
    a specific model (useful for the routing roadmap); omitted when not
    meaningful (e.g. a cumulative total that could span calls to more
    than one model, though no client actually does that yet).

    cache_write_tokens/cache_read_tokens (Task 23.1) are NOT included in
    input_tokens -- they're separate, additive components of a call's
    total input. This is a cross-vendor invariant every client enforces
    at the point it builds a Usage (Task 23.7): Anthropic's own SDK
    reports input_tokens as already the *uncached* portion (verified
    against anthropic.lib.tools._beta_runner's own usage-totaling code),
    but OpenAI's prompt_tokens and Gemini's prompt_token_count are
    *inclusive* of cache activity on the wire -- those two clients
    subtract the cached portion back out before constructing a Usage,
    so input_tokens means the same thing regardless of vendor. Both
    cache fields default 0 so a Usage with no cache activity (or from a
    vendor/path that doesn't report it) is unaffected.
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str | None = None
    cache_write_tokens: int = Field(ge=0, default=0)
    cache_read_tokens: int = Field(ge=0, default=0)

    @property
    def total_tokens(self) -> int:
        """Derived, not stored -- the true all-in token count: input +
        output + cache_write_tokens + cache_read_tokens (Task 23.7).
        Cache tokens are never part of input_tokens (see class
        docstring), so they'd be silently dropped from this total if
        not added explicitly here.
        """
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )

    @property
    def cache_hit_rate(self) -> float:
        """Fraction of this call's total input tokens served from cache.

        Total input is input_tokens (uncached) + cache_write_tokens +
        cache_read_tokens (see class docstring). 0.0 on a Usage with no
        input-side tokens at all, rather than raising. This formula
        relies on input_tokens being exclusive of cache activity for
        every vendor -- true since Task 23.7 normalized OpenAI/Gemini to
        match Anthropic's already-exclusive convention (prior to that,
        this understated the true rate for those two vendors).
        """
        total_input = self.input_tokens + self.cache_write_tokens + self.cache_read_tokens
        if total_input == 0:
            return 0.0
        return self.cache_read_tokens / total_input

    def __add__(self, other: "Usage") -> "Usage":
        """Combines two usage records -- e.g. a repair-retry's call
        summed with the original, so a caller sees the total cost of
        satisfying one request, not just its last underlying API call.
        """
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            model=other.model,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
        )
