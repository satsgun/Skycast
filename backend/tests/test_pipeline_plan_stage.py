from datetime import datetime, timezone

import pytest

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    ProviderCapabilities,
    TimeWindow,
    WeatherVariable,
)
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.errors import NoCapableProviderError, NoLocationError
from skycast.pipeline.plan import PlannedTool
from skycast.pipeline.plan_stage import plan
from skycast.providers.base import WeatherProvider
from skycast.providers.in_memory import InMemoryProvider


class _StubProvider(WeatherProvider):
    def __init__(self, capabilities: ProviderCapabilities) -> None:
        self._capabilities = capabilities

    async def geocode(self, name: str) -> list[Location]:
        raise NotImplementedError("plan must never call geocode")

    async def fetch_forecast(
        self, location: Location, request: ForecastRequest
    ) -> Forecast:
        raise NotImplementedError("plan must never call fetch_forecast")

    def capabilities(self) -> ProviderCapabilities:
        return self._capabilities


def _full_capabilities(**overrides) -> ProviderCapabilities:
    defaults = dict(
        max_forecast_days=16,
        available_variables=set(WeatherVariable),
        supports_geocoding=True,
    )
    defaults.update(overrides)
    return ProviderCapabilities(**defaults)


def _spec(**overrides) -> DataNeedsSpec:
    defaults = dict(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    defaults.update(overrides)
    return DataNeedsSpec(**defaults)


def _location(name: str = "Hyderabad") -> Location:
    return Location(
        id=f"in-memory:{name.lower()}", name=name,
        latitude=17.385, longitude=78.4867, timezone="Asia/Kolkata",
    )


def test_single_location_by_name_produces_a_two_call_chain() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"open-meteo": InMemoryProvider()}

    result = plan(spec, providers)

    assert len(result.calls) == 2
    geocode, forecast = result.calls
    assert geocode.tool is PlannedTool.GEOCODE
    assert geocode.location_name == "Hyderabad"
    assert geocode.provider == "open-meteo"
    assert forecast.tool is PlannedTool.FETCH_FORECAST
    assert forecast.depends_on == [geocode.call_id]
    assert forecast.provider == "open-meteo"
    assert forecast.request == ForecastRequest(
        granularities=spec.granularities, window=spec.window, variables=spec.variables
    )
    assert result.intent == spec.intent


def test_default_location_with_known_coords_skips_geocode() -> None:
    spec = _spec(location_names=[])
    providers = {"open-meteo": InMemoryProvider()}
    default = _location()

    result = plan(spec, providers, default_location=default)

    assert len(result.calls) == 1
    call = result.calls[0]
    assert call.tool is PlannedTool.FETCH_FORECAST
    assert call.location == default
    assert call.depends_on == []


def test_no_location_and_no_default_raises_no_location_error() -> None:
    spec = _spec(location_names=[])
    providers = {"open-meteo": InMemoryProvider()}

    with pytest.raises(NoLocationError) as exc_info:
        plan(spec, providers, default_location=None)

    assert exc_info.value.reason == "no_location_and_no_default"


def test_comparison_produces_two_independent_parallel_chains() -> None:
    spec = _spec(
        location_names=["Miami", "Seattle"], intent=QueryIntent.COMPARISON
    )
    providers = {"open-meteo": InMemoryProvider()}

    result = plan(spec, providers)

    assert len(result.calls) == 4
    geocode_a, forecast_a, geocode_b, forecast_b = result.calls
    assert geocode_a.location_name == "Miami"
    assert forecast_a.depends_on == [geocode_a.call_id]
    assert geocode_b.location_name == "Seattle"
    assert forecast_b.depends_on == [geocode_b.call_id]
    all_ids = {c.call_id for c in result.calls}
    assert geocode_b.call_id not in forecast_a.depends_on
    assert geocode_a.call_id not in forecast_b.depends_on
    assert all_ids == {geocode_a.call_id, forecast_a.call_id, geocode_b.call_id, forecast_b.call_id}


def test_needs_geocoding_true_reaches_select_provider_for_name_target() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"stub": _StubProvider(_full_capabilities(supports_geocoding=False))}

    with pytest.raises(NoCapableProviderError) as exc_info:
        plan(spec, providers)

    assert exc_info.value.reason == "geocoding_not_supported"


def test_needs_geocoding_false_for_coords_known_target_ignores_geocoding_support() -> None:
    spec = _spec(location_names=[])
    providers = {"stub": _StubProvider(_full_capabilities(supports_geocoding=False))}

    result = plan(spec, providers, default_location=_location())

    assert len(result.calls) == 1
    assert result.calls[0].provider == "stub"


def test_provider_id_recovered_by_reverse_lookup() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {
        "a": _StubProvider(_full_capabilities(available_variables=set())),
        "b": _StubProvider(_full_capabilities()),
    }

    result = plan(spec, providers)

    assert all(call.provider == "b" for call in result.calls)


def test_no_capable_provider_error_propagates_unmodified() -> None:
    spec = _spec(variables={WeatherVariable.PRECIP_PROBABILITY})
    providers = {
        "stub": _StubProvider(_full_capabilities(available_variables={WeatherVariable.TEMPERATURE}))
    }

    with pytest.raises(NoCapableProviderError) as exc_info:
        plan(spec, providers)

    assert exc_info.value.reason == "missing_variables"


def test_resolved_locations_for_one_of_two_names_produces_mixed_chain() -> None:
    spec = _spec(location_names=["Mumbai", "Delhi"], intent=QueryIntent.COMPARISON)
    providers = {"open-meteo": InMemoryProvider()}
    mumbai = _location("Mumbai")

    result = plan(spec, providers, resolved_locations={"Mumbai": mumbai})

    assert len(result.calls) == 3
    forecast_mumbai, geocode_delhi, forecast_delhi = result.calls
    assert forecast_mumbai.tool is PlannedTool.FETCH_FORECAST
    assert forecast_mumbai.location == mumbai
    assert forecast_mumbai.location_name == "Mumbai"
    assert forecast_mumbai.depends_on == []
    assert geocode_delhi.tool is PlannedTool.GEOCODE
    assert geocode_delhi.location_name == "Delhi"
    assert forecast_delhi.depends_on == [geocode_delhi.call_id]


def test_resolved_locations_entry_not_matching_a_name_is_ignored() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"open-meteo": InMemoryProvider()}

    result = plan(spec, providers, resolved_locations={"Springfield": _location("Springfield")})

    assert len(result.calls) == 2
    geocode, forecast = result.calls
    assert geocode.tool is PlannedTool.GEOCODE
    assert geocode.location_name == "Hyderabad"
    assert forecast.depends_on == [geocode.call_id]


def test_resolved_locations_used_as_targets_when_location_names_empty() -> None:
    spec = _spec(location_names=[])
    providers = {"open-meteo": InMemoryProvider()}
    springfield = _location("Springfield")

    result = plan(spec, providers, resolved_locations={"Springfield": springfield})

    assert len(result.calls) == 1
    call = result.calls[0]
    assert call.tool is PlannedTool.FETCH_FORECAST
    assert call.location == springfield
    assert call.location_name == "Springfield"
    assert call.depends_on == []


def test_resolved_locations_wins_over_default_location_when_location_names_empty() -> None:
    spec = _spec(location_names=[])
    providers = {"open-meteo": InMemoryProvider()}
    springfield = _location("Springfield")
    default = _location("Hyderabad")

    result = plan(
        spec, providers, default_location=default, resolved_locations={"Springfield": springfield}
    )

    assert len(result.calls) == 1
    assert result.calls[0].location == springfield


def test_default_location_chain_has_no_location_name() -> None:
    spec = _spec(location_names=[])
    providers = {"open-meteo": InMemoryProvider()}

    result = plan(spec, providers, default_location=_location())

    assert result.calls[0].location_name is None


def test_determinism_same_inputs_produce_equal_plan() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"open-meteo": InMemoryProvider()}

    first = plan(spec, providers)
    second = plan(spec, providers)

    assert first == second
