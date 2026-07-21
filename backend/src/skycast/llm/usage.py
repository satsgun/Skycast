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
    """

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str | None = None

    @property
    def total_tokens(self) -> int:
        """Derived, not stored -- input + output for this usage record."""
        return self.input_tokens + self.output_tokens

    def __add__(self, other: "Usage") -> "Usage":
        """Combines two usage records -- e.g. a repair-retry's call
        summed with the original, so a caller sees the total cost of
        satisfying one request, not just its last underlying API call.
        """
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            model=other.model,
        )
