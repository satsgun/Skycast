"""SSE payload models for the FE<->BE wire contract (ADR-0003, Task 13.2).

One frozen Pydantic v2 model per SSE event type, carried in that event's
envelope `data` field (Task 13.3 defines the envelope itself). Imports
only from the domain layer (Location, Forecast) -- no pipeline, no
provider, no FastAPI -- so these stay pure and testable independent of
the orchestrator that will eventually produce them (Phase 5).
"""

from datetime import date
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

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


class AnswerCard(BaseModel):
    """Structured card data for the UI: the full resolved Forecast as-is
    (no slimmer projection -- the FE picks what to render) plus a hint at
    which reading the answer text is about.
    """

    model_config = ConfigDict(frozen=True)

    forecast: Forecast
    highlight: AwareDatetime | date | None = None


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
