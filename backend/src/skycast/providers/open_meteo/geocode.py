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
    locations = [_to_location(result) for result in results]
    return _drop_unpopulated_noise(locations)


def _drop_unpopulated_noise(locations: list[Location]) -> list[Location]:
    """Open-Meteo's search does plain prefix/fuzzy-name matching with no
    relevance weighting, so a short query can pull in obscure,
    population-less villages alongside a legitimate, heavily-populated
    match (e.g. "NYC" prefix-matches the Swedish hamlet "Nyckleby" --
    Issue #91). When at least one result carries real population data,
    the population-less ones are almost certainly this kind of noise, so
    drop them. Leaves an all-populated or all-population-less batch
    untouched -- there's no signal to prefer one over another in either
    case (e.g. "LA" matches only population-less villages; a genuinely
    ambiguous well-known name like "Springfield" returns all-populated
    candidates).
    """
    populated = [loc for loc in locations if loc.population is not None]
    if not populated or len(populated) == len(locations):
        return locations
    return populated


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
