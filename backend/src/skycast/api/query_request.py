"""QueryRequest: the /query POST body model (Task 18.1).

FastAPI's typed inbound contract for POST /query, mirroring the SSE
outbound contract (Task 13). The backend is stateless (CLAUDE.md) --
every per-turn fact the pipeline needs (the query text, the client's own
clock, location defaults/overrides) arrives here on each request.
"""

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from skycast.domain.location import Location
from skycast.pipeline.session_context import SessionContext


class QueryRequest(BaseModel):
    """POST /query body.

    `resolved_location` is a disambiguation re-query: the coordinates
    the user tapped on a prior `clarify`. A one-shot per-request
    override, not session carry-over -- it does not belong in
    SessionContext, and this class only carries it faithfully. Intended
    mechanism (implemented by run_query, Task 18.3): run_query supplies
    `resolved_location` as an already-coordinates target, so it flows
    through plan()'s existing skip-geocode path -- no new plan()
    parameter, no location_names mutation.
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1)
    now: AwareDatetime
    default_location: Location | None = None
    resolved_location: Location | None = None
    units: str | None = None

    def to_session_context(self) -> SessionContext:
        """Builds the SessionContext pipeline stages consume.

        Deliberately drops `resolved_location` -- SessionContext has no
        field for it (see class docstring); it isn't session carry-over.
        `carried_location_name`/`carried_window` are left at their
        SessionContext defaults (None) -- QueryRequest has no source
        fields for multi-turn carry-over in v1.
        """
        return SessionContext(
            now=self.now, default_location=self.default_location, units_hint=self.units
        )
