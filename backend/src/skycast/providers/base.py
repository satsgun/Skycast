"""Abstract provider contract for the WeatherProvider seam (ADR-0002,
Task 11).

Every concrete provider (InMemoryProvider — Task 12; OpenMeteoProvider —
Phase 6) implements this ABC. Above this seam, the agent/pipeline speak
only in these domain types; below it, each provider translates to/from
its own native API. Never reference a concrete provider's specifics here.
"""

from abc import ABC, abstractmethod

from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.domain.provider import ForecastRequest, ProviderCapabilities


class WeatherProvider(ABC):
    """Provider-agnostic contract for geocoding and forecast retrieval."""

    @abstractmethod
    async def geocode(self, name: str) -> list[Location]:
        """Resolve a free-text place name to zero or more candidate Locations.

        Empty list = no match — never a Location with null/placeholder
        coordinates. Order best-match-first if the provider implies
        ranking. Raises ProviderError if the provider is unreachable or
        returns a malformed response.
        """
        ...

    @abstractmethod
    async def fetch_forecast(
        self, location: Location, request: ForecastRequest
    ) -> Forecast:
        """Fetch a Forecast for `location` satisfying `request`.

        Populates exactly the blocks implied by `request.granularities`.
        Raises ProviderError on an unreachable/failed provider — never
        returns a partial or empty Forecast to signal failure.
        """
        ...

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return this provider's capabilities.

        Static per-provider declaration for v1 — synchronous, no I/O.
        """
        ...
