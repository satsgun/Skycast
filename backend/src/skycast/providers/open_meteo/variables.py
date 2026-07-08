"""Open-Meteo variable-name mapping (Task 19.1).

The single source of Open-Meteo's forecast parameter names -- nothing
outside this module knows them. Canonical WeatherVariable (Task 11)
maps differently per block: hourly is one param each; daily has no
single "value" for TEMPERATURE, only max/min extremes, so it expands to
a pair of daily params. FEELS_LIKE has no daily param at all -- see
_DAILY_PARAMS below.
"""

from skycast.domain.provider import WeatherVariable

_HOURLY_PARAMS: dict[WeatherVariable, tuple[str, ...]] = {
    WeatherVariable.TEMPERATURE: ("temperature_2m",),
    WeatherVariable.FEELS_LIKE: ("apparent_temperature",),
    WeatherVariable.PRECIP_PROBABILITY: ("precipitation_probability",),
    WeatherVariable.PRECIP_AMOUNT: ("precipitation",),
    WeatherVariable.WIND_SPEED: ("wind_speed_10m",),
    WeatherVariable.CONDITION: ("weather_code",),
}

# FEELS_LIKE has no daily param -- DailyReading (Task 10) has no
# feels-like field, so this table intentionally has no entry for it.
# _params() below skips any variable absent from its table rather than
# raising, so a daily request for FEELS_LIKE is silently omitted from
# the daily block instead of being mapped to a param nothing will read.
_DAILY_PARAMS: dict[WeatherVariable, tuple[str, ...]] = {
    WeatherVariable.TEMPERATURE: ("temperature_2m_max", "temperature_2m_min"),
    WeatherVariable.PRECIP_PROBABILITY: ("precipitation_probability_max",),
    WeatherVariable.PRECIP_AMOUNT: ("precipitation_sum",),
    WeatherVariable.WIND_SPEED: ("wind_speed_10m_max",),
    WeatherVariable.CONDITION: ("weather_code",),
}

# condition_code is a required (non-optional) field on every reading
# (Task 10), so weather_code must always be requested regardless of
# whether the caller asked for WeatherVariable.CONDITION. Daily also
# always carries sunrise/sunset (optional DailyReading fields, but
# Open-Meteo always returns them for the daily block).
_ALWAYS_HOURLY: tuple[str, ...] = ("weather_code",)
_ALWAYS_DAILY: tuple[str, ...] = ("weather_code", "sunrise", "sunset")


def hourly_params(variables: set[WeatherVariable]) -> list[str]:
    """Open-Meteo `hourly=` param list for the requested variables."""
    return _params(variables, _HOURLY_PARAMS, _ALWAYS_HOURLY)


def daily_params(variables: set[WeatherVariable]) -> list[str]:
    """Open-Meteo `daily=` param list for the requested variables."""
    return _params(variables, _DAILY_PARAMS, _ALWAYS_DAILY)


def _params(
    variables: set[WeatherVariable],
    table: dict[WeatherVariable, tuple[str, ...]],
    always: tuple[str, ...],
) -> list[str]:
    result: list[str] = []
    for param in always:
        if param not in result:
            result.append(param)
    for variable in WeatherVariable:  # stable order regardless of set order
        if variable not in variables:
            continue
        for param in table.get(variable, ()):  # absent = no param for this block
            if param not in result:
                result.append(param)
    return result
