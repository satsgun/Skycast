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

    `resolved_locations` is a disambiguation re-query: a name->Location
    map of every location the user has already resolved in this
    multi-round clarify sub-flow (fix #90) -- both a prior round's picks
    and the one just tapped on the latest `clarify`, keyed by the
    original query-named location they answer for. A one-shot
    per-request override, not session carry-over -- it does not belong
    in SessionContext, and this class only carries it faithfully.
    run_query passes it straight through to plan()'s own
    resolved_locations parameter, which skips geocoding for any matching
    name and geocodes the rest as usual.
    """

    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1)
    now: AwareDatetime
    default_location: Location | None = None
    resolved_locations: dict[str, Location] = Field(default_factory=dict)
    units: str | None = None

    def to_session_context(self) -> SessionContext:
        """Builds the SessionContext pipeline stages consume.

        Deliberately drops `resolved_locations` -- SessionContext has no
        field for it (see class docstring); it isn't session carry-over.
        `carried_location_name`/`carried_window` are left at their
        SessionContext defaults (None) -- QueryRequest has no source
        fields for multi-turn carry-over in v1.
        """
        return SessionContext(
            now=self.now, default_location=self.default_location, units_hint=self.units
        )
