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
    resolved_locations: dict[str, Location] | None = None,
) -> ToolPlan:
    """Raises NoLocationError if spec.location_names is empty and neither
    resolved_locations nor default_location supplies a target.
    Raises NoCapableProviderError (via select_provider) if no registered
    provider can serve some chain.

    resolved_locations is a name->Location map of locations already
    disambiguated in an earlier round (fix #90): each spec.location_names
    entry found there skips geocoding and becomes a pre-resolved chain
    (still carrying its name, so a later NeedsClarification can recover
    it -- see execute_stage._resolved_locations), while the rest still
    geocode by name as usual. It also wins over default_location when
    location_names is empty, preserving the existing single-location
    disambiguation override even if decompose's re-run produced no names
    at all.

    A location_names entry that isn't in resolved_locations but names the
    same place as default_location also skips geocoding (fix #94):
    decompose is instructed to leave location_names empty when a default
    location covers the query, but isn't always reliable about it -- and
    re-geocoding a bare name that happens to equal the default location's
    own name can hit the exact ambiguity default_location exists to avoid
    (e.g. "Hyderabad" alone matches 5 different cities worldwide).
    resolved_locations still wins when both apply.
    """
    targets = _resolve_targets(
        spec, default_location=default_location, resolved_locations=resolved_locations
    )
    # TODO(Task 21.3/21.4): spec.time is a descriptor, not a concrete
    # window -- decompose no longer resolves one (ADR-0006). Until the
    # resolver is wired in post-geocode, window is always None here, so
    # ForecastRequest construction below fails its own validator for any
    # HOURLY/DAILY spec. Known, accepted gap; see
    # test_pipeline_plan_stage.py's pinning test.
    request = ForecastRequest(
        granularities=spec.granularities, window=None, variables=spec.variables
    )

    calls: list[PlannedCall] = []
    for index, (name, target) in enumerate(targets):
        is_name = isinstance(target, str)
        selected = select_provider(
            required_variables=spec.variables,
            granularities=spec.granularities,
            window=None,
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
                    location_name=name,
                    request=request,
                )
            )

    return ToolPlan(calls=calls, intent=spec.intent)


def _resolve_targets(
    spec: DataNeedsSpec,
    *,
    default_location: Location | None,
    resolved_locations: dict[str, Location] | None,
) -> list[tuple[str | None, str | Location]]:
    resolved = resolved_locations or {}
    if spec.location_names:
        return [
            (name, _resolve_one(name, resolved, default_location))
            for name in spec.location_names
        ]
    if resolved:
        return list(resolved.items())
    if default_location is not None:
        return [(None, default_location)]
    raise NoLocationError(
        "query named no location and no default location is configured",
        reason="no_location_and_no_default",
    )


def _resolve_one(
    name: str, resolved: dict[str, Location], default_location: Location | None
) -> str | Location:
    if name in resolved:
        return resolved[name]
    if default_location is not None and _same_place(name, default_location.name):
        return default_location
    return name


def _same_place(name: str, default_name: str) -> bool:
    return name.strip().lower() == default_name.strip().lower()
