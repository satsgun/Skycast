"""plan: pipeline stage 2 (Task 15.3).

Turns a DataNeedsSpec into an explicit ToolPlan: one geocode->forecast
chain per target location (fanned out in parallel for a comparison),
each chain's provider chosen via select_provider (Task 15.2). Pure,
deterministic, synchronous -- no LLM, no network, no provider I/O (only
capabilities() is read, via select_provider).
"""

from skycast.domain.location import Location
from skycast.domain.provider import ForecastRequest
from skycast.pipeline.data_needs import DataNeedsSpec
from skycast.pipeline.errors import NoLocationError
from skycast.pipeline.plan import PlannedCall, PlannedTool, ToolPlan
from skycast.pipeline.provider_selection import select_provider
from skycast.providers.base import WeatherProvider


def plan(
    spec: DataNeedsSpec,
    providers: dict[str, WeatherProvider],
    *,
    default_location: Location | None = None,
) -> ToolPlan:
    """Raises NoLocationError if spec.location_names is empty and
    default_location is None. Raises NoCapableProviderError (via
    select_provider) if no registered provider can serve some chain.
    """
    targets = _resolve_targets(spec, default_location=default_location)
    request = ForecastRequest(
        granularities=spec.granularities, window=spec.window, variables=spec.variables
    )

    calls: list[PlannedCall] = []
    for index, target in enumerate(targets):
        is_name = isinstance(target, str)
        selected = select_provider(
            required_variables=spec.variables,
            granularities=spec.granularities,
            window=spec.window,
            providers=list(providers.values()),
            needs_geocoding=is_name,
        )
        provider_id = next(pid for pid, p in providers.items() if p is selected)

        if is_name:
            geocode_id = f"geocode-{index}"
            calls.append(
                PlannedCall(
                    call_id=geocode_id,
                    tool=PlannedTool.GEOCODE,
                    provider=provider_id,
                    location_name=target,
                )
            )
            calls.append(
                PlannedCall(
                    call_id=f"forecast-{index}",
                    tool=PlannedTool.FETCH_FORECAST,
                    provider=provider_id,
                    depends_on=[geocode_id],
                    request=request,
                )
            )
        else:
            calls.append(
                PlannedCall(
                    call_id=f"forecast-{index}",
                    tool=PlannedTool.FETCH_FORECAST,
                    provider=provider_id,
                    location=target,
                    request=request,
                )
            )

    return ToolPlan(calls=calls, intent=spec.intent)


def _resolve_targets(
    spec: DataNeedsSpec, *, default_location: Location | None
) -> list[str | Location]:
    if spec.location_names:
        return list(spec.location_names)
    if default_location is not None:
        return [default_location]
    raise NoLocationError(
        "query named no location and no default location is configured",
        reason="no_location_and_no_default",
    )
