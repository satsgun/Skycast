"""SessionContext: query-time context the frontend sends up alongside a
natural-language query (Task 14.5).

The backend is stateless (CLAUDE.md) -- session state lives client-side,
so every field a pipeline stage needs to resolve relative time,
defaults, and conversational continuity must arrive here on each
request. `now` exists so decompose never reads the wall clock directly
(Task 14's constraint: deterministic tests). Deliberately minimal --
expand as later stages need more.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict

from skycast.domain.location import Location
from skycast.domain.provider import TimeWindow


class SessionContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    now: AwareDatetime
    default_location: Location | None = None
    units_hint: str | None = None
    carried_location_name: str | None = None
    carried_window: TimeWindow | None = None
