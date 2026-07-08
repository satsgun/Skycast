"""Open-Meteo capabilities declaration (Task 19.5).

Standalone function, not yet a WeatherProvider method -- see
geocode.py's docstring for why.
"""

from skycast.domain.provider import ProviderCapabilities, WeatherVariable

_MAX_FORECAST_DAYS = 16


def capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        max_forecast_days=_MAX_FORECAST_DAYS,
        available_variables=set(WeatherVariable),
        supports_geocoding=True,
        # Open-Meteo's free tier doesn't publish a hard per-minute rate
        # limit for this use case -- left unset per the ticket rather
        # than guessing an advisory number with no source.
        rate_limit_per_minute=None,
    )
