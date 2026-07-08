"""Open-Meteo variable-name mapping (Task 19.1, extended by 19.4).

The single source of Open-Meteo's forecast parameter names -- nothing
outside this module knows them. Canonical WeatherVariable (Task 11)
maps differently per block: hourly/daily/current each have their own
table. TEMPERATURE always expands into every block's always-included
set (HourlyReading.temperature / DailyReading.temp_min/temp_max are
required, non-optional fields -- same reasoning as weather_code, just
missed when 19.1 was first written). FEELS_LIKE has no daily param at
all, and PRECIP_PROBABILITY has no current param at all -- see the
tables below.
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

# PRECIP_PROBABILITY has no current param -- Open-Meteo's current=
# block has no probability field at all (probability requires a
# forecast-model spread; "right now" has none). Same
# skip-if-absent-from-table mechanism as daily FEELS_LIKE above.
_CURRENT_PARAMS: dict[WeatherVariable, tuple[str, ...]] = {
    WeatherVariable.TEMPERATURE: ("temperature_2m",),
    WeatherVariable.FEELS_LIKE: ("apparent_temperature",),
    WeatherVariable.PRECIP_AMOUNT: ("precipitation",),
    WeatherVariable.WIND_SPEED: ("wind_speed_10m",),
    WeatherVariable.CONDITION: ("weather_code",),
}

# condition_code and temperature are required (non-optional) fields on
# every reading (Task 10), so weather_code and temperature_2m must
# always be requested regardless of which WeatherVariables the caller
# asked for. Daily also always carries sunrise/sunset (optional
# DailyReading fields, but Open-Meteo always returns them for the
# daily block) and its own max/min temperature pair.
_ALWAYS_HOURLY: tuple[str, ...] = ("weather_code", "temperature_2m")
_ALWAYS_DAILY: tuple[str, ...] = (
    "weather_code",
    "sunrise",
    "sunset",
    "temperature_2m_max",
    "temperature_2m_min",
)
_ALWAYS_CURRENT: tuple[str, ...] = ("weather_code", "temperature_2m")


def hourly_params(variables: set[WeatherVariable]) -> list[str]:
    """Open-Meteo `hourly=` param list for the requested variables."""
    return _params(variables, _HOURLY_PARAMS, _ALWAYS_HOURLY)


def daily_params(variables: set[WeatherVariable]) -> list[str]:
    """Open-Meteo `daily=` param list for the requested variables."""
    return _params(variables, _DAILY_PARAMS, _ALWAYS_DAILY)


def current_params(variables: set[WeatherVariable]) -> list[str]:
    """Open-Meteo `current=` param list for the requested variables."""
    return _params(variables, _CURRENT_PARAMS, _ALWAYS_CURRENT)


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
