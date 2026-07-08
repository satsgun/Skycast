"""SynthesisOutput: the LLM's structured output for pipeline stage 4,
synthesize (Task 17.2).

The only thing the synthesize LLM call returns -- prose plus a pointer
into the stage-3 Forecast(s), never forecast data itself, so provider
data can't be altered by passing through the LLM. Reuses Highlight/
ReadingLocator from sse/payloads.py (Task 17.1) rather than a parallel
type, since synthesize (Task 17.3) assembles AnswerCard from this same
Highlight paired with the trusted Forecast(s) -- the LLM's pointer and
the card's pointer must be the same shape. Checking forecast_index
against the real forecast count happens in synthesize, not here -- this
model alone doesn't know the forecast count.
"""

from pydantic import BaseModel, ConfigDict, Field

from skycast.sse.payloads import Highlight


class SynthesisOutput(BaseModel):
    """Tool schema for the synthesize LLM call."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    highlight: Highlight | None = None
