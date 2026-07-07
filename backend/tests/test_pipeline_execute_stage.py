import asyncio
from datetime import datetime, timezone

import pytest

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    ProviderCapabilities,
    WeatherVariable,
)
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.execute_result import Failed, NeedsClarification, Success
from skycast.pipeline.execute_stage import _prioritize, _run_with_fail_fast, execute
from skycast.pipeline.plan_stage import plan
from skycast.providers.base import WeatherProvider
from skycast.providers.errors import ProviderError
from skycast.providers.in_memory import InMemoryProvider
from skycast.sse.payloads import ErrorKind, PipelineStage
from tests.helpers import RecordingEmitter


def _spec(**overrides) -> DataNeedsSpec:
    defaults = dict(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.CONDITIONS,
    )
    defaults.update(overrides)
    return DataNeedsSpec(**defaults)


def _location(name: str, lat: float = 0.0, lon: float = 0.0) -> Location:
    return Location(
        id=f"test:{name.lower()}", name=name, latitude=lat, longitude=lon, timezone="UTC"
    )


def _run(coro):
    return asyncio.run(coro)


def _full_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        max_forecast_days=16,
        available_variables=set(WeatherVariable),
        supports_geocoding=True,
    )


class _GeocodeSpyProvider(InMemoryProvider):
    async def geocode(self, name: str) -> list[Location]:
        raise AssertionError("geocode must not be called for a preset-location chain")


def test_happy_single_chain_by_name() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"open-meteo": InMemoryProvider()}
    built_plan = plan(spec, providers)
    emitter = RecordingEmitter()

    result = _run(execute(built_plan, providers, emit=emitter))

    assert isinstance(result, Success)
    assert len(result.forecasts) == 1
    assert [stage for _, stage in emitter.calls] == [
        PipelineStage.EXECUTE_GEOCODE,
        PipelineStage.EXECUTE_FORECAST,
    ]


def test_skip_geocode_chain_makes_no_geocode_call() -> None:
    spec = _spec(location_names=[])
    providers = {"open-meteo": _GeocodeSpyProvider()}
    default = _location("Hyderabad", 17.385, 78.4867)
    built_plan = plan(spec, providers, default_location=default)
    emitter = RecordingEmitter()

    result = _run(execute(built_plan, providers, emit=emitter))

    assert isinstance(result, Success)
    assert [stage for _, stage in emitter.calls] == [PipelineStage.EXECUTE_FORECAST]


def test_zero_matches_is_not_found() -> None:
    spec = _spec(location_names=["Nowhereville"])
    providers = {"open-meteo": InMemoryProvider()}
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, Failed)
    assert result.kind == ErrorKind.NOT_FOUND
    assert result.for_location_name == "Nowhereville"


def test_ambiguous_match_needs_clarification() -> None:
    spec = _spec(location_names=["Springfield"])
    providers = {"open-meteo": InMemoryProvider()}
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, NeedsClarification)
    assert len(result.candidates) == 3
    assert result.for_location_name == "Springfield"


def test_forecast_provider_outage_is_provider_unreachable() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"open-meteo": InMemoryProvider(fail_forecast=True)}
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, Failed)
    assert result.kind == ErrorKind.PROVIDER_UNREACHABLE


def test_geocode_provider_outage_is_provider_unreachable() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"open-meteo": InMemoryProvider(fail_geocode=True)}
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, Failed)
    assert result.kind == ErrorKind.PROVIDER_UNREACHABLE


def _comparison_providers() -> dict[str, WeatherProvider]:
    provider = InMemoryProvider(
        locations={
            "miami": [_location("Miami", 25.7617, -80.1918)],
            "seattle": [_location("Seattle", 47.6062, -122.3321)],
        }
    )
    return {"open-meteo": provider}


def test_comparison_happy_path_two_forecasts_in_chain_order() -> None:
    spec = _spec(
        location_names=["Miami", "Seattle"], intent=QueryIntent.COMPARISON
    )
    providers = _comparison_providers()
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, Success)
    assert len(result.forecasts) == 2
    assert result.forecasts[0].location.name == "Miami"
    assert result.forecasts[1].location.name == "Seattle"


class _InterleavingProvider(WeatherProvider):
    def __init__(self, events: list[str], locations: dict[str, Location]) -> None:
        self._events = events
        self._locations = locations

    async def geocode(self, name: str) -> list[Location]:
        key = name.strip().lower()
        self._events.append(f"geocode-start:{key}")
        await asyncio.sleep(0)
        self._events.append(f"geocode-end:{key}")
        location = self._locations.get(key)
        return [location] if location is not None else []

    async def fetch_forecast(self, location: Location, request: ForecastRequest) -> Forecast:
        raise NotImplementedError

    def capabilities(self) -> ProviderCapabilities:
        return _full_capabilities()


def test_independent_geocode_chains_run_concurrently() -> None:
    events: list[str] = []
    provider = _InterleavingProvider(
        events,
        {
            "miami": _location("Miami", 25.7617, -80.1918),
            "seattle": _location("Seattle", 47.6062, -122.3321),
        },
    )
    providers = {"open-meteo": provider}
    spec = _spec(location_names=["Miami", "Seattle"], intent=QueryIntent.COMPARISON)
    built_plan = plan(spec, providers)

    # execute() will fail at the forecast phase (fetch_forecast unimplemented),
    # but the geocode phase's concurrency already happened by then.
    with pytest.raises(NotImplementedError):
        _run(execute(built_plan, providers, emit=RecordingEmitter()))

    starts = [e for e in events if e.startswith("geocode-start")]
    ends = [e for e in events if e.startswith("geocode-end")]
    assert len(starts) == 2
    assert len(ends) == 2
    start_indices = [events.index(s) for s in starts]
    end_indices = [events.index(e) for e in ends]
    assert max(start_indices) < min(end_indices), (
        "both geocode calls should start before either finishes -- proves "
        "genuine interleaving, not sequential execution"
    )


def test_comparison_ambiguous_plus_success_needs_clarification() -> None:
    provider = InMemoryProvider(
        locations={
            "springfield": [
                _location("Springfield", 39.78, -89.65),
                _location("Springfield", 37.20, -93.29),
            ],
            "miami": [_location("Miami", 25.7617, -80.1918)],
        }
    )
    providers = {"open-meteo": provider}
    spec = _spec(location_names=["Springfield", "Miami"], intent=QueryIntent.COMPARISON)
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, NeedsClarification)
    assert result.for_location_name == "Springfield"


class _SlowThenClarifyFastFailProvider(WeatherProvider):
    """First geocode call (name_a) is ambiguous but slow; second (name_b)
    fails fast with ProviderError. Used to prove the slow ambiguous
    chain is cancelled once the fast provider_unreachable is known.
    """

    def __init__(self, name_a: str, name_b: str, completed: list[str]) -> None:
        self._name_a = name_a.lower()
        self._name_b = name_b.lower()
        self._completed = completed

    async def geocode(self, name: str) -> list[Location]:
        key = name.strip().lower()
        if key == self._name_a:
            await asyncio.sleep(0.05)
            self._completed.append(key)
            return [_location("A1", 1, 1), _location("A2", 2, 2)]
        if key == self._name_b:
            raise ProviderError("simulated outage")
        return []

    async def fetch_forecast(self, location: Location, request: ForecastRequest) -> Forecast:
        raise NotImplementedError

    def capabilities(self) -> ProviderCapabilities:
        return _full_capabilities()


def test_comparison_provider_unreachable_wins_over_ambiguous_and_cancels_slow_sibling() -> None:
    completed: list[str] = []
    provider = _SlowThenClarifyFastFailProvider("ambiguous-city", "failing-city", completed)
    providers = {"open-meteo": provider}
    spec = _spec(location_names=["ambiguous-city", "failing-city"], intent=QueryIntent.COMPARISON)
    built_plan = plan(spec, providers)

    result = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert isinstance(result, Failed)
    assert result.kind == ErrorKind.PROVIDER_UNREACHABLE
    assert completed == []  # the slow ambiguous chain was cancelled before finishing


def test_unknown_provider_id_is_internal_error() -> None:
    spec = _spec(location_names=["Hyderabad"])
    built_plan = plan(spec, {"open-meteo": InMemoryProvider()})

    result = _run(execute(built_plan, {"other-id": InMemoryProvider()}, emit=RecordingEmitter()))

    assert isinstance(result, Failed)
    assert result.kind == ErrorKind.INTERNAL


def test_unknown_provider_id_on_skip_geocode_chain_is_internal_error() -> None:
    # A coords-known chain has no geocode call, so this is the only path
    # that can exercise _run_forecast's own unknown-provider-id branch
    # (a name-based chain always hits _run_geocode's check first).
    spec = _spec(location_names=[])
    default = _location("Hyderabad", 17.385, 78.4867)
    built_plan = plan(spec, {"open-meteo": InMemoryProvider()}, default_location=default)

    result = _run(execute(built_plan, {"other-id": InMemoryProvider()}, emit=RecordingEmitter()))

    assert isinstance(result, Failed)
    assert result.kind == ErrorKind.INTERNAL


def test_determinism_same_plan_and_providers_produce_equal_result() -> None:
    spec = _spec(location_names=["Hyderabad"])
    fixed_now = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    providers = {"open-meteo": InMemoryProvider(now=lambda: fixed_now)}
    built_plan = plan(spec, providers)

    first = _run(execute(built_plan, providers, emit=RecordingEmitter()))
    second = _run(execute(built_plan, providers, emit=RecordingEmitter()))

    assert first == second


# --- _prioritize unit tests ---


def test_prioritize_empty_returns_none() -> None:
    assert _prioritize([]) is None


def test_prioritize_all_clear_returns_none() -> None:
    location = _location("X")
    assert _prioritize([location]) is None


def test_prioritize_provider_unreachable_beats_needs_clarification() -> None:
    failed = Failed(kind=ErrorKind.PROVIDER_UNREACHABLE, message="outage")
    clarify = NeedsClarification(candidates=[_location("A"), _location("B")], for_location_name="x")

    assert _prioritize([clarify, failed]) is failed
    assert _prioritize([failed, clarify]) is failed


def test_prioritize_needs_clarification_beats_other_failed() -> None:
    clarify = NeedsClarification(candidates=[_location("A"), _location("B")], for_location_name="x")
    not_found = Failed(kind=ErrorKind.NOT_FOUND, message="no match")

    assert _prioritize([not_found, clarify]) is clarify


def test_prioritize_first_in_order_tie_break() -> None:
    first = Failed(kind=ErrorKind.NOT_FOUND, message="first")
    second = Failed(kind=ErrorKind.INTERNAL, message="second")

    assert _prioritize([first, second]) is first


# --- _run_with_fail_fast unit test ---


def test_run_with_fail_fast_cancels_slow_coroutine() -> None:
    completed: list[str] = []

    async def fast_failure():
        return Failed(kind=ErrorKind.PROVIDER_UNREACHABLE, message="fast fail")

    async def slow():
        await asyncio.sleep(0.05)
        completed.append("slow")
        return "should not happen"

    results = _run(_run_with_fail_fast([slow(), fast_failure()]))

    assert completed == []
    assert any(
        isinstance(r, Failed) and r.kind == ErrorKind.PROVIDER_UNREACHABLE for r in results
    )
