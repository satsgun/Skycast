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
from skycast.domain.provider import ForecastRequest
from skycast.pipeline.data_needs import QueryIntent


class PlannedTool(StrEnum):
    GEOCODE = "GEOCODE"
    FETCH_FORECAST = "FETCH_FORECAST"


class PlannedCall(BaseModel):
    """One tool invocation in a ToolPlan.

    location_name is set for a GEOCODE call (the name to resolve) and
    must be None for FETCH_FORECAST. For FETCH_FORECAST, request is
    always the executable request; location is set only when coords are
    already known and geocode was skipped -- whether the alternative
    (a geocode dependency will supply the location) holds is a
    cross-call fact, checked by ToolPlan, not here.
    """

    model_config = ConfigDict(frozen=True)

    call_id: str
    tool: PlannedTool
    provider: str
    depends_on: list[str] = Field(default_factory=list)
    location_name: str | None = None
    location: Location | None = None
    request: ForecastRequest | None = None

    @model_validator(mode="after")
    def _require_fields_consistent_with_tool(self) -> "PlannedCall":
        if self.tool == PlannedTool.GEOCODE:
            if self.location_name is None:
                raise ValueError("a GEOCODE call requires location_name")
            if self.location is not None or self.request is not None:
                raise ValueError("a GEOCODE call must not set location or request")
        else:
            if self.location_name is not None:
                raise ValueError("a FETCH_FORECAST call must not set location_name")
            if self.request is None:
                raise ValueError("a FETCH_FORECAST call requires request")
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
