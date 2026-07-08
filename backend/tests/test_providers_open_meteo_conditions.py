import pytest

from skycast.domain.conditions import ConditionCode
from skycast.providers.open_meteo.conditions import _WMO_TO_CONDITION, map_condition_code

_TABLE_CASES = [
    (0, ConditionCode.CLEAR),
    (1, ConditionCode.MAINLY_CLEAR),
    (2, ConditionCode.PARTLY_CLOUDY),
    (3, ConditionCode.CLOUDY),
    (45, ConditionCode.FOG),
    (48, ConditionCode.FOG),
    (51, ConditionCode.DRIZZLE),
    (53, ConditionCode.DRIZZLE),
    (55, ConditionCode.DRIZZLE),
    (56, ConditionCode.FREEZING_DRIZZLE),
    (57, ConditionCode.FREEZING_DRIZZLE),
    (61, ConditionCode.RAIN),
    (63, ConditionCode.RAIN),
    (65, ConditionCode.HEAVY_RAIN),
    (66, ConditionCode.FREEZING_RAIN),
    (67, ConditionCode.FREEZING_RAIN),
    (71, ConditionCode.SNOW),
    (73, ConditionCode.SNOW),
    (77, ConditionCode.SNOW),
    (75, ConditionCode.HEAVY_SNOW),
    (80, ConditionCode.RAIN_SHOWERS),
    (81, ConditionCode.RAIN_SHOWERS),
    (82, ConditionCode.RAIN_SHOWERS),
    (85, ConditionCode.SNOW_SHOWERS),
    (86, ConditionCode.SNOW_SHOWERS),
    (95, ConditionCode.THUNDERSTORM),
    (96, ConditionCode.THUNDERSTORM),
    (99, ConditionCode.THUNDERSTORM),
]


@pytest.mark.parametrize("weather_code,expected", _TABLE_CASES)
def test_maps_documented_wmo_code_to_condition_code(
    weather_code: int, expected: ConditionCode
) -> None:
    assert map_condition_code(weather_code) is expected


@pytest.mark.parametrize("weather_code", [4, -1, 1000])
def test_unmapped_code_returns_unknown(weather_code: int) -> None:
    assert map_condition_code(weather_code) is ConditionCode.UNKNOWN


def test_every_condition_code_except_unknown_is_reachable() -> None:
    assert set(_WMO_TO_CONDITION.values()) == set(ConditionCode) - {
        ConditionCode.UNKNOWN
    }
