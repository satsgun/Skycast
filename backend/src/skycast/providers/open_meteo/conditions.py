"""WMO weather-code -> ConditionCode mapping (Task 19.2).

Open-Meteo returns WMO 4677 "weather_code" integers; this is the only
place that dialect is translated to canonical ConditionCode (Task 8).
"""

from skycast.domain.conditions import ConditionCode

_WMO_TO_CONDITION: dict[int, ConditionCode] = {
    0: ConditionCode.CLEAR,
    1: ConditionCode.MAINLY_CLEAR,
    2: ConditionCode.PARTLY_CLOUDY,
    3: ConditionCode.CLOUDY,
    45: ConditionCode.FOG,
    48: ConditionCode.FOG,
    51: ConditionCode.DRIZZLE,
    53: ConditionCode.DRIZZLE,
    55: ConditionCode.DRIZZLE,
    56: ConditionCode.FREEZING_DRIZZLE,
    57: ConditionCode.FREEZING_DRIZZLE,
    61: ConditionCode.RAIN,
    63: ConditionCode.RAIN,
    65: ConditionCode.HEAVY_RAIN,
    66: ConditionCode.FREEZING_RAIN,
    67: ConditionCode.FREEZING_RAIN,
    71: ConditionCode.SNOW,
    73: ConditionCode.SNOW,
    77: ConditionCode.SNOW,
    75: ConditionCode.HEAVY_SNOW,
    80: ConditionCode.RAIN_SHOWERS,
    81: ConditionCode.RAIN_SHOWERS,
    82: ConditionCode.RAIN_SHOWERS,
    85: ConditionCode.SNOW_SHOWERS,
    86: ConditionCode.SNOW_SHOWERS,
    95: ConditionCode.THUNDERSTORM,
    96: ConditionCode.THUNDERSTORM,
    99: ConditionCode.THUNDERSTORM,
}


def map_condition_code(weather_code: int) -> ConditionCode:
    """Map an Open-Meteo WMO weather_code to canonical ConditionCode.

    Unmapped/unknown codes -> UNKNOWN, never raise (Task 8's contract).
    """
    return _WMO_TO_CONDITION.get(weather_code, ConditionCode.UNKNOWN)
