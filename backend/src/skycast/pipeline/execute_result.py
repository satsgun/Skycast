"""ExecutionResult: the typed outcome of pipeline stage 3, execute
(Task 16.1).

execute() (Task 16.2) returns exactly one of these three variants -- the
orchestrator (Phase 5) pattern-matches on the concrete class to choose
the terminal SSE event (answer/clarify/error). Clarification is a
first-class outcome here, not an exception: it's normal control flow
for the ask-before-guessing UX (CLAUDE.md), not a failure.
"""

from pydantic import BaseModel, ConfigDict, Field

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.sse.payloads import ErrorKind


class Success(BaseModel):
    """One Forecast per chain, in the plan's chain order (comparison ->
    multiple). Non-empty.
    """

    model_config = ConfigDict(frozen=True)

    forecasts: list[Forecast] = Field(min_length=1)


class NeedsClarification(BaseModel):
    """A geocode step matched 2+ candidates; ask the user which one."""

    model_config = ConfigDict(frozen=True)

    candidates: list[Location] = Field(min_length=2)
    for_location_name: str


class Failed(BaseModel):
    """Execution could not produce a result for at least one chain
    (all-or-nothing for multi-chain plans -- Task 16 design decision).
    """

    model_config = ConfigDict(frozen=True)

    kind: ErrorKind
    message: str
    for_location_name: str | None = None


ExecutionResult = Success | NeedsClarification | Failed
