"""PlannedCall and ToolPlan: the typed output of pipeline stage 2, plan
(Task 15.1).

Stage 2 (not yet built, Task 15.2+) turns a DataNeedsSpec into a
ToolPlan: an explicit, ordered sequence of tool calls stage 3 (execute)
runs, with per-call dependencies and a selected provider per chain.
Deterministic, rule-based -- imports no LLMClient (ADR-0001's
separate-stages reasoning is about routing/eval living in distinct
stages, not about plan needing to be an LLM call).
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from skycast.domain.location import Location
from skycast.domain.provider import Granularity, WeatherVariable
from skycast.pipeline.data_needs import QueryIntent
from skycast.pipeline.relative_time import RelativeTimeSpec


class PlannedTool(StrEnum):
    GEOCODE = "GEOCODE"
    FETCH_FORECAST = "FETCH_FORECAST"


class PlannedCall(BaseModel):
    """One tool invocation in a ToolPlan.

    location_name is set for a GEOCODE call (the name to resolve). For
    FETCH_FORECAST, granularities/variables are always the executable
    request's ingredients; location is set only when coords are already
    known and geocode was skipped -- whether the alternative (a geocode
    dependency will supply the location) holds is a cross-call fact,
    checked by ToolPlan, not here. A FETCH_FORECAST call may also carry
    location_name alongside location -- the query-named location this
    pre-resolved chain answers for -- but only together with location;
    never alone (that shape stays a GEOCODE-call-only concept).

    granularities/variables/time are not assembled into a ForecastRequest
    here: time is a descriptor (ADR-0006), not yet a concrete window --
    resolving it requires a timezone this chain doesn't have until
    execute() knows its Location (post-geocode, or immediately for a
    skip-geocode chain). execute() builds the real ForecastRequest right
    before calling fetch_forecast.
    """

    model_config = ConfigDict(frozen=True)

    call_id: str
    tool: PlannedTool
    provider: str
    depends_on: list[str] = Field(default_factory=list)
    location_name: str | None = None
    location: Location | None = None
    granularities: set[Granularity] | None = None
    variables: set[WeatherVariable] | None = None
    time: RelativeTimeSpec | None = None

    @model_validator(mode="after")
    def _require_fields_consistent_with_tool(self) -> "PlannedCall":
        if self.tool == PlannedTool.GEOCODE:
            if self.location_name is None:
                raise ValueError("a GEOCODE call requires location_name")
            if (
                self.location is not None
                or self.granularities is not None
                or self.variables is not None
                or self.time is not None
            ):
                raise ValueError(
                    "a GEOCODE call must not set location or forecast-request fields"
                )
        else:
            if self.location_name is not None and self.location is None:
                raise ValueError(
                    "a FETCH_FORECAST call may only set location_name together with location"
                )
            if self.granularities is None or self.variables is None:
                raise ValueError(
                    "a FETCH_FORECAST call requires granularities and variables"
                )
            needs_time = {Granularity.HOURLY, Granularity.DAILY} & self.granularities
            if needs_time and self.time is None:
                raise ValueError(
                    "a FETCH_FORECAST call requires time when granularities "
                    "includes HOURLY or DAILY"
                )
        return self


class ToolPlan(BaseModel):
    """The whole stage-2 plan: ordered tool calls plus the query's intent.

    `calls`' list order is topological-friendly but `depends_on` is the
    source of truth for ordering; calls with no dependency relationship
    may run in parallel (e.g. comparison fan-out).
    """

    model_config = ConfigDict(frozen=True)

    calls: list[PlannedCall]
    intent: QueryIntent

    @model_validator(mode="after")
    def _require_depends_on_reference_existing_calls(self) -> "ToolPlan":
        call_ids = {call.call_id for call in self.calls}
        for call in self.calls:
            for dep in call.depends_on:
                if dep not in call_ids:
                    raise ValueError(
                        f"call {call.call_id!r} depends_on unknown call_id {dep!r}"
                    )
        return self

    @model_validator(mode="after")
    def _require_no_cycles(self) -> "ToolPlan":
        calls_by_id = {call.call_id: call for call in self.calls}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(call_id: str) -> None:
            if call_id in visited:
                return
            if call_id in visiting:
                raise ValueError(f"cycle detected in depends_on involving {call_id!r}")
            visiting.add(call_id)
            for dep in calls_by_id[call_id].depends_on:
                visit(dep)
            visiting.discard(call_id)
            visited.add(call_id)

        for call in self.calls:
            visit(call.call_id)
        return self

    @model_validator(mode="after")
    def _require_fetch_forecast_location_source_is_unambiguous(self) -> "ToolPlan":
        calls_by_id = {call.call_id: call for call in self.calls}
        for call in self.calls:
            if call.tool != PlannedTool.FETCH_FORECAST:
                continue
            has_location = call.location is not None
            has_geocode_dependency = any(
                calls_by_id[dep].tool == PlannedTool.GEOCODE for dep in call.depends_on
            )
            if has_location and has_geocode_dependency:
                raise ValueError(
                    f"call {call.call_id!r} has both location and a geocode dependency"
                )
            if not has_location and not has_geocode_dependency:
                raise ValueError(
                    f"call {call.call_id!r} has neither location nor a geocode dependency"
                )
        return self
