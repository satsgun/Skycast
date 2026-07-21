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
from skycast.pipeline.errors import NoCapableProviderError
from skycast.pipeline.provider_selection import _rank, select_provider
from skycast.providers.base import WeatherProvider
from skycast.providers.in_memory import InMemoryProvider


class _StubProvider(WeatherProvider):
    def __init__(self, capabilities: ProviderCapabilities, name: str = "stub") -> None:
        self._capabilities = capabilities
        self.name = name

    async def geocode(self, name: str) -> list[Location]:
        raise NotImplementedError("select_provider must never call geocode")

    async def fetch_forecast(
        self, location: Location, request: ForecastRequest
    ) -> Forecast:
        raise NotImplementedError("select_provider must never call fetch_forecast")

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


def test_single_capable_provider_is_selected() -> None:
    provider = InMemoryProvider()

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )

    assert selected is provider


def test_missing_variable_raises_no_capable_provider_error() -> None:
    provider = _StubProvider(_full_capabilities(available_variables={WeatherVariable.TEMPERATURE}))

    with pytest.raises(NoCapableProviderError) as exc_info:
        select_provider(
            required_variables={WeatherVariable.PRECIP_PROBABILITY},
            granularities={Granularity.CURRENT},
            window=None,
            horizon_days=None,
            providers=[provider],
            needs_geocoding=False,
        )

    assert exc_info.value.reason == "missing_variables"


def test_needs_geocoding_true_with_unsupported_provider_raises() -> None:
    provider = _StubProvider(_full_capabilities(supports_geocoding=False))

    with pytest.raises(NoCapableProviderError) as exc_info:
        select_provider(
            required_variables={WeatherVariable.TEMPERATURE},
            granularities={Granularity.CURRENT},
            window=None,
            horizon_days=None,
            providers=[provider],
            needs_geocoding=True,
        )

    assert exc_info.value.reason == "geocoding_not_supported"


def test_needs_geocoding_false_ignores_unsupported_geocoding() -> None:
    provider = _StubProvider(_full_capabilities(supports_geocoding=False))

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )

    assert selected is provider


def test_window_beyond_max_forecast_days_raises() -> None:
    provider = _StubProvider(_full_capabilities(max_forecast_days=1))
    start = datetime(2026, 7, 7, tzinfo=timezone.utc)
    window = TimeWindow(start=start, end=start.replace(day=12))

    with pytest.raises(NoCapableProviderError) as exc_info:
        select_provider(
            required_variables={WeatherVariable.TEMPERATURE},
            granularities={Granularity.DAILY},
            window=window,
            horizon_days=None,
            providers=[provider],
            needs_geocoding=False,
        )

    assert exc_info.value.reason == "forecast_horizon_too_short"


def test_horizon_days_beyond_max_forecast_days_raises() -> None:
    provider = _StubProvider(_full_capabilities(max_forecast_days=16))

    with pytest.raises(NoCapableProviderError) as exc_info:
        select_provider(
            required_variables={WeatherVariable.TEMPERATURE},
            granularities={Granularity.DAILY},
            window=None,
            horizon_days=20,
            providers=[provider],
            needs_geocoding=False,
        )

    assert exc_info.value.reason == "forecast_horizon_too_short"


def test_horizon_days_within_max_forecast_days_is_accepted() -> None:
    provider = _StubProvider(_full_capabilities(max_forecast_days=16))

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.DAILY},
        window=None,
        horizon_days=16,
        providers=[provider],
        needs_geocoding=False,
    )

    assert selected is provider


def test_none_horizon_days_never_triggers_horizon_check() -> None:
    provider = _StubProvider(_full_capabilities(max_forecast_days=0))

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )

    assert selected is provider


def test_none_window_never_triggers_horizon_check() -> None:
    provider = _StubProvider(_full_capabilities(max_forecast_days=0))

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )

    assert selected is provider


def test_granularity_is_not_filtered() -> None:
    provider = InMemoryProvider()

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.HOURLY, Granularity.DAILY},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )

    assert selected is provider


def test_empty_providers_list_raises_no_providers_registered() -> None:
    with pytest.raises(NoCapableProviderError) as exc_info:
        select_provider(
            required_variables={WeatherVariable.TEMPERATURE},
            granularities={Granularity.CURRENT},
            window=None,
            horizon_days=None,
            providers=[],
            needs_geocoding=False,
        )

    assert exc_info.value.reason == "no_providers_registered"


def test_two_capable_providers_picks_the_ranked_top() -> None:
    first = _StubProvider(_full_capabilities(), name="first")
    second = _StubProvider(_full_capabilities(), name="second")

    selected = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[first, second],
        needs_geocoding=False,
    )

    assert selected is first


def test_rank_is_order_preserving_identity_hook() -> None:
    first = _StubProvider(_full_capabilities(), name="first")
    second = _StubProvider(_full_capabilities(), name="second")

    assert _rank([first, second]) == [first, second]


def test_determinism_same_inputs_select_same_provider() -> None:
    provider = InMemoryProvider()

    first = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )
    second = select_provider(
        required_variables={WeatherVariable.TEMPERATURE},
        granularities={Granularity.CURRENT},
        window=None,
        horizon_days=None,
        providers=[provider],
        needs_geocoding=False,
    )

    assert first is second is provider
