"""RelativeTimeSpec: the query's time intent, decoupled from any
timezone (Task 21.1, ADR-0006).

Decompose runs before geocoding, so it has no reliable timezone for a
freshly-named location -- resolving "this evening" into concrete UTC
bounds at that point either guesses the caller's own timezone or leans
on the LLM's general knowledge of a city's offset (fragile near DST
boundaries, unreliable for obscure places). RelativeTimeSpec captures
*what* time window the query means without committing to *when* that is
in absolute terms; a resolver (Task 21.3) turns it into a concrete
TimeWindow once the target's real timezone is known, post-geocode. Pure
vocabulary only -- no resolution logic lives here.
"""

from datetime import time as _time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RelativeTimeKind(StrEnum):
    NOW = "NOW"
    TODAY = "TODAY"
    THIS_EVENING = "THIS_EVENING"
    TOMORROW = "TOMORROW"
    NEXT_N_DAYS = "NEXT_N_DAYS"
    ABSOLUTE = "ABSOLUTE"


class RelativeTimeSpec(BaseModel):
    """A query's time intent, still missing only a timezone.

    day_count is required for, and only valid for, NEXT_N_DAYS: how many
    calendar days the window spans, starting today (e.g. 3 for "the next
    3 days"). clock_time is required for, and only valid for, ABSOLUTE:
    an explicit wall-clock time the user named (e.g. "2 PM tomorrow" ->
    clock_time=14:00, day_offset=1); day_offset defaults to 0 (today)
    and is only meaningful alongside ABSOLUTE.
    """

    model_config = ConfigDict(frozen=True)

    kind: RelativeTimeKind
    day_count: int | None = Field(default=None, ge=1)
    clock_time: _time | None = None
    day_offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _require_params_consistent_with_kind(self) -> "RelativeTimeSpec":
        if self.kind == RelativeTimeKind.NEXT_N_DAYS:
            if self.day_count is None:
                raise ValueError("NEXT_N_DAYS requires day_count")
        elif self.day_count is not None:
            raise ValueError(f"day_count is not valid for {self.kind}")

        if self.kind == RelativeTimeKind.ABSOLUTE:
            if self.clock_time is None:
                raise ValueError("ABSOLUTE requires clock_time")
        elif self.clock_time is not None or self.day_offset != 0:
            raise ValueError(f"clock_time/day_offset are not valid for {self.kind}")

        return self
