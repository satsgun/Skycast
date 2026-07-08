"""SSE payload models for the FE<->BE wire contract (ADR-0003, Task 13.2).

One frozen Pydantic v2 model per SSE event type, carried in that event's
envelope `data` field (Task 13.3 defines the envelope itself). Imports
only from the domain layer (Location, Forecast) -- no pipeline, no
provider, no FastAPI -- so these stay pure and testable independent of
the orchestrator that will eventually produce them (Phase 5).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location


class PipelineStage(StrEnum):
    DECOMPOSE = "decompose"
    PLAN = "plan"
    EXECUTE_GEOCODE = "execute_geocode"
    EXECUTE_FORECAST = "execute_forecast"
    SYNTHESIZE = "synthesize"


class StepPayload(BaseModel):
    """A non-terminal progress update for the thinking-state UI."""

    model_config = ConfigDict(frozen=True)

    label: str
    stage: PipelineStage


class ClarifyPayload(BaseModel):
    """Terminal: multiple geocode matches; the FE renders these as one-tap
    options. Fewer than 2 candidates is a bug -- a single match wouldn't
    need clarification.
    """

    model_config = ConfigDict(frozen=True)

    candidates: list[Location] = Field(min_length=2)


class ForecastBlock(StrEnum):
    CURRENT = "current"
    HOURLY = "hourly"
    DAILY = "daily"


class ReadingLocator(BaseModel):
    """Identifies a reading within a Forecast without duplicating its
    data. `current` is a single reading (index must be None); `hourly`
    and `daily` are series (index is the position within that series).
    """

    model_config = ConfigDict(frozen=True)

    block: ForecastBlock
    index: int | None = None

    @model_validator(mode="after")
    def _require_index_consistent_with_block(self) -> "ReadingLocator":
        if self.block == ForecastBlock.CURRENT:
            if self.index is not None:
                raise ValueError("current block is a single reading; index must be None")
        elif self.index is None or self.index < 0:
            raise ValueError(f"{self.block.value} block requires a non-negative index")
        return self


class Highlight(BaseModel):
    """Points at one reading in one of AnswerCard.forecasts."""

    model_config = ConfigDict(frozen=True)

    forecast_index: int = Field(ge=0)
    locator: ReadingLocator


class AnswerCard(BaseModel):
    """Structured card data for the UI: the resolved Forecast(s) as-is
    (no slimmer projection -- the FE picks what to render) plus a hint at
    which reading, in which forecast, the answer text is about.
    """

    model_config = ConfigDict(frozen=True)

    forecasts: list[Forecast] = Field(min_length=1)
    highlight: Highlight | None = None


class AnswerPayload(BaseModel):
    """Terminal: the answer-first conclusion plus its supporting card."""

    model_config = ConfigDict(frozen=True)

    text: str
    card: AnswerCard


class ErrorKind(StrEnum):
    NOT_FOUND = "not_found"
    PROVIDER_UNREACHABLE = "provider_unreachable"
    BAD_INPUT = "bad_input"
    INTERNAL = "internal"


class ErrorPayload(BaseModel):
    """Terminal: a machine-readable error kind plus a display message."""

    model_config = ConfigDict(frozen=True)

    kind: ErrorKind
    message: str
