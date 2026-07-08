"""Open-Meteo geocoding (Task 19.3).

Standalone async function, not yet a WeatherProvider method --
OpenMeteoProvider can't be instantiated (ABC, all 3 methods required)
until 19.4/19.5 also exist. `client` is injected so tests can point it
at an httpx.MockTransport instead of the real network.
"""

import httpx

from skycast.domain.location import Location
from skycast.providers.errors import ProviderError

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_RESULT_COUNT = 5


async def geocode(client: httpx.AsyncClient, name: str) -> list[Location]:
    try:
        response = await client.get(
            _GEOCODING_URL, params={"name": name, "count": _RESULT_COUNT}
        )
    except httpx.HTTPError as exc:
        raise ProviderError(
            f"Open-Meteo geocoding request failed: {exc}",
            reason=type(exc).__name__,
        ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise ProviderError(
            "Open-Meteo geocoding returned a malformed response",
            reason="malformed_response",
        ) from exc

    if body.get("error"):
        raise ProviderError(
            body.get("reason", "Open-Meteo geocoding returned an error"),
            reason="provider_error",
        )

    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ProviderError(
            f"Open-Meteo geocoding returned HTTP {response.status_code}",
            reason="http_error",
        ) from exc

    results = body.get("results") or []
    return [_to_location(result) for result in results]


def _to_location(result: dict) -> Location:
    return Location(
        id=str(result["id"]),
        name=result["name"],
        latitude=result["latitude"],
        longitude=result["longitude"],
        country=result.get("country"),
        country_code=result.get("country_code"),
        admin1=result.get("admin1"),
        admin2=result.get("admin2"),
        population=result.get("population"),
        timezone=result.get("timezone"),
    )
