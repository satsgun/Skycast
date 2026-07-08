import asyncio
import os

import httpx
import pytest

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.domain.provider import (
    ForecastRequest,
    Granularity,
    ProviderCapabilities,
    WeatherVariable,
)
from skycast.providers.base import WeatherProvider
from skycast.providers.open_meteo.provider import _DEFAULT_TIMEOUT, OpenMeteoProvider


def _run(coro):
    return asyncio.run(coro)


def _mock_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _json_handler(body: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    return handler


def test_satisfies_weather_provider_contract() -> None:
    provider = OpenMeteoProvider(client=_mock_client(_json_handler({})))

    assert isinstance(provider, WeatherProvider)


def test_default_construction_builds_a_real_client_with_sane_timeout() -> None:
    provider = OpenMeteoProvider()

    assert isinstance(provider._client, httpx.AsyncClient)
    assert provider._client.timeout == _DEFAULT_TIMEOUT


def test_injected_client_is_used_directly() -> None:
    injected = _mock_client(_json_handler({}))

    provider = OpenMeteoProvider(client=injected)

    assert provider._client is injected


def test_geocode_delegates_to_geocode_module() -> None:
    body = {
        "results": [
            {"id": 1, "name": "Tokyo", "latitude": 35.6895, "longitude": 139.69171}
        ]
    }
    provider = OpenMeteoProvider(client=_mock_client(_json_handler(body)))

    result = _run(provider.geocode("Tokyo"))

    assert result == [
        Location(id="1", name="Tokyo", latitude=35.6895, longitude=139.69171)
    ]


def test_fetch_forecast_delegates_to_forecast_module() -> None:
    body = {
        "timezone": "Asia/Kolkata",
        "current": {
            "time": "2026-07-08T12:00",
            "temperature_2m": 31.0,
            "weather_code": 61,
        },
    }
    provider = OpenMeteoProvider(client=_mock_client(_json_handler(body)))
    location = Location(id="test:hyd", name="Hyderabad", latitude=17.385, longitude=78.4867)
    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )

    forecast = _run(provider.fetch_forecast(location, request))

    assert isinstance(forecast, Forecast)
    assert forecast.current.temperature == 31.0


def test_capabilities_delegates_to_capabilities_module() -> None:
    provider = OpenMeteoProvider(client=_mock_client(_json_handler({})))

    result = provider.capabilities()

    assert isinstance(result, ProviderCapabilities)
    assert result.max_forecast_days == 16
    assert result.supports_geocoding is True


def test_attribution_constant() -> None:
    assert OpenMeteoProvider.ATTRIBUTION == "Weather data by Open-Meteo.com"


@pytest.mark.skipif(
    not os.environ.get("SKYCAST_LIVE_OPEN_METEO_TESTS"),
    reason="opt-in live network test; set SKYCAST_LIVE_OPEN_METEO_TESTS=1 to run",
)
def test_live_geocode_and_current_forecast_for_a_known_city() -> None:  # pragma: no cover
    provider = OpenMeteoProvider()

    locations = _run(provider.geocode("London"))
    assert len(locations) >= 1

    request = ForecastRequest(
        granularities={Granularity.CURRENT}, variables={WeatherVariable.TEMPERATURE}
    )
    forecast = _run(provider.fetch_forecast(locations[0], request))
    assert forecast.current is not None
