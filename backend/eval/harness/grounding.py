"""Fixture-fact derivation (Task E4.1): turns a real Forecast fixture
into the qualitative facts a grounded synthesize answer must respect.

Pure and deterministic -- reads only the fixture, no LLM. This is the
"expected" side of grounding: a check (Task E4.2) compares an answer's
prose against these facts, not against raw numbers -- grounding is
about qualitative consistency, not reciting figures (Task E4's own
scope note).
"""

from __future__ import annotations

from dataclasses import dataclass

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import DailyReading, Forecast, HourlyReading
from skycast.sse.payloads import ForecastBlock, ReadingLocator

# Editorial ground truth (Task E4.1): these thresholds and bands encode
# what a correct answer should say, not hidden magic numbers.
_RAIN_LIKELY_THRESHOLD = 50.0  # precip_probability >= this -> rain likely
_WINDY_THRESHOLD_KMH = 25.0  # wind_speed(_max) >= this -> windy

_COLD_MAX_C = 10.0  # temp < this -> cold
_MILD_MAX_C = 20.0  # this <= temp < _WARM_MAX_C -> mild
_WARM_MAX_C = 28.0  # this <= temp -> hot; below -> warm

# Total over every ConditionCode member -- "unknown" is a 6th family
# beyond the ticket's core five, necessary since ConditionCode.UNKNOWN
# is a real value a provider mapping can produce.
_CONDITION_FAMILY: dict[ConditionCode, str] = {
    ConditionCode.CLEAR: "clear",
    ConditionCode.MAINLY_CLEAR: "clear",
    ConditionCode.PARTLY_CLOUDY: "cloud",
    ConditionCode.CLOUDY: "cloud",
    ConditionCode.FOG: "cloud",
    ConditionCode.DRIZZLE: "rain",
    ConditionCode.FREEZING_DRIZZLE: "rain",
    ConditionCode.RAIN: "rain",
    ConditionCode.HEAVY_RAIN: "rain",
    ConditionCode.FREEZING_RAIN: "rain",
    ConditionCode.RAIN_SHOWERS: "rain",
    ConditionCode.SNOW: "snow",
    ConditionCode.HEAVY_SNOW: "snow",
    ConditionCode.SNOW_SHOWERS: "snow",
    ConditionCode.THUNDERSTORM: "storm",
    ConditionCode.UNKNOWN: "unknown",
}

_Reading = HourlyReading | DailyReading


@dataclass(frozen=True)
class GroundingFacts:
    """Qualitative facts the selected reading supports -- what a
    grounded answer about it must not contradict.

    rain_likely/windy are None when the underlying reading has no value
    for that dimension (precip_probability/wind_speed(_max) weren't
    populated) -- "unknown," not "false": a grounding check can't flag a
    contradiction on a dimension with no ground truth (the "contradiction,
    not omission" rule, Task E4.2). temperature_band/condition_family are
    always derivable -- temperature/temp_max and condition_code are never
    optional on either reading type.
    """

    rain_likely: bool | None
    temperature_band: str
    condition_family: str
    windy: bool | None


def derive_facts(forecast: Forecast, locator: ReadingLocator | None = None) -> GroundingFacts:
    """Derives GroundingFacts from the reading `locator` points at.

    Reading selection when `locator` is None: `forecast.current` if
    present, else the first hourly reading, else the first daily
    reading -- the same "what's this answer most likely about"
    precedence used elsewhere in the pipeline.
    """
    reading = _select_reading(forecast, locator)
    return GroundingFacts(
        rain_likely=_rain_likely(reading),
        temperature_band=_temperature_band(reading),
        condition_family=_CONDITION_FAMILY[reading.condition_code],
        windy=_windy(reading),
    )


def _select_reading(forecast: Forecast, locator: ReadingLocator | None) -> _Reading:
    if locator is not None:
        if locator.block == ForecastBlock.CURRENT:
            assert forecast.current is not None
            return forecast.current
        if locator.block == ForecastBlock.HOURLY:
            assert forecast.hourly is not None and locator.index is not None
            return forecast.hourly[locator.index]
        assert forecast.daily is not None and locator.index is not None
        return forecast.daily[locator.index]

    if forecast.current is not None:
        return forecast.current
    if forecast.hourly:
        return forecast.hourly[0]
    assert forecast.daily
    return forecast.daily[0]


def _rain_likely(reading: _Reading) -> bool | None:
    if reading.precip_probability is None:
        return None
    return reading.precip_probability >= _RAIN_LIKELY_THRESHOLD


def _temperature_band(reading: _Reading) -> str:
    temp = reading.temperature if isinstance(reading, HourlyReading) else reading.temp_max
    if temp < _COLD_MAX_C:
        return "cold"
    if temp < _MILD_MAX_C:
        return "mild"
    if temp < _WARM_MAX_C:
        return "warm"
    return "hot"


def _windy(reading: _Reading) -> bool | None:
    wind = reading.wind_speed if isinstance(reading, HourlyReading) else reading.wind_speed_max
    if wind is None:
        return None
    return wind >= _WINDY_THRESHOLD_KMH
