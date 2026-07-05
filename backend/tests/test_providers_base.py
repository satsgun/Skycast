import asyncio
from datetime import datetime, timezone

import pytest

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    ProviderCapabilities,
    WeatherVariable,
)
from skycast.providers.base import WeatherProvider


def _location() -> Location:
    return Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6)


def _forecast() -> Forecast:
    return Forecast(
        location=_location(),
        units=Units(),
        current=HourlyReading(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            temperature=20.0,
            condition_code=ConditionCode.CLEAR,
        ),
    )


def _capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        max_forecast_days=16,
        available_variables={WeatherVariable.TEMPERATURE},
        supports_geocoding=True,
    )


class _FakeProvider(WeatherProvider):
    async def geocode(self, name: str) -> list[Location]:
        return [_location()]

    async def fetch_forecast(
        self, location: Location, request: ForecastRequest
    ) -> Forecast:
        return _forecast()

    def capabilities(self) -> ProviderCapabilities:
        return _capabilities()


def test_weather_provider_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        WeatherProvider()


def test_concrete_subclass_implementing_all_methods_can_be_instantiated() -> None:
    provider = _FakeProvider()
    assert isinstance(provider, WeatherProvider)


def test_fake_provider_geocode_returns_locations() -> None:
    provider = _FakeProvider()
    result = asyncio.run(provider.geocode("Springfield"))
    assert result == [_location()]


def test_fake_provider_fetch_forecast_returns_forecast() -> None:
    provider = _FakeProvider()
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    result = asyncio.run(provider.fetch_forecast(_location(), request))
    assert result == _forecast()


def test_fake_provider_capabilities_returns_provider_capabilities() -> None:
    provider = _FakeProvider()
    assert provider.capabilities() == _capabilities()
