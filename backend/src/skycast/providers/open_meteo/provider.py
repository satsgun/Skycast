"""OpenMeteoProvider: the real WeatherProvider implementation against
the Open-Meteo API (Task 19, assembled in 19.6).

Thin delegation to the standalone geocode()/fetch_forecast()/
capabilities() functions (19.3/19.4/19.5) -- this class's only real
job is owning a shared httpx.AsyncClient across calls and satisfying
the WeatherProvider contract so it can be instantiated at all.
"""

import httpx

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.domain.provider import ForecastRequest, ProviderCapabilities
from skycast.providers.base import WeatherProvider
from skycast.providers.open_meteo import capabilities as _capabilities
from skycast.providers.open_meteo import forecast as _forecast
from skycast.providers.open_meteo import geocode as _geocode

# Generous relative to httpx's 5s default -- forecast responses can
# carry many days of hourly data; connect fails fast, everything else
# gets more room.
_DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class OpenMeteoProvider(WeatherProvider):
    """CC BY 4.0 licence requires attribution -- ATTRIBUTION is exposed
    as a constant here; rendering it is the frontend's job."""

    ATTRIBUTION = "Weather data by Open-Meteo.com"

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = (
            client
            if client is not None
            else httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT)
        )

    async def geocode(self, name: str) -> list[Location]:
        return await _geocode.geocode(self._client, name)

    async def fetch_forecast(
        self, location: Location, request: ForecastRequest
    ) -> Forecast:
        return await _forecast.fetch_forecast(self._client, location, request)

    def capabilities(self) -> ProviderCapabilities:
        return _capabilities.capabilities()
