"""Open-Meteo geocoding (Task 19.3).

Standalone async function, not yet a WeatherProvider method --
OpenMeteoProvider can't be instantiated (ABC, all 3 methods required)
until 19.4/19.5 also exist. `client` is injected so tests can point it
at an httpx.MockTransport instead of the real network.
"""

import httpx

from skycast.domain.location import Location
from skycast.providers.open_meteo._http import get_json

_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_RESULT_COUNT = 5


async def geocode(client: httpx.AsyncClient, name: str) -> list[Location]:
    body = await get_json(
        client, _GEOCODING_URL, params={"name": name, "count": _RESULT_COUNT}
    )
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
