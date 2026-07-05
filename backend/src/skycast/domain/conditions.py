from enum import StrEnum
import json
from pathlib import Path


class ConditionCode(StrEnum):
    CLEAR = "CLEAR"
    MAINLY_CLEAR = "MAINLY_CLEAR"
    PARTLY_CLOUDY = "PARTLY_CLOUDY"
    CLOUDY = "CLOUDY"
    FOG = "FOG"
    DRIZZLE = "DRIZZLE"
    FREEZING_DRIZZLE = "FREEZING_DRIZZLE"
    RAIN = "RAIN"
    HEAVY_RAIN = "HEAVY_RAIN"
    FREEZING_RAIN = "FREEZING_RAIN"
    SNOW = "SNOW"
    HEAVY_SNOW = "HEAVY_SNOW"
    RAIN_SHOWERS = "RAIN_SHOWERS"
    SNOW_SHOWERS = "SNOW_SHOWERS"
    THUNDERSTORM = "THUNDERSTORM"
    UNKNOWN = "UNKNOWN"


def condition_codes_as_json() -> str:
    return json.dumps([member.value for member in ConditionCode])


# Regenerated dev-time artifact, not read back at runtime by anything today.
# If a future task reads this file from an installed (non-editable) package,
# it'll need `[tool.setuptools.package-data]` in pyproject.toml — Render's
# build (`pip install .`) won't otherwise ship non-.py files in the wheel.
_CONDITIONS_JSON_PATH = Path(__file__).with_name("conditions.json")


def write_condition_codes_json(path: Path = _CONDITIONS_JSON_PATH) -> None:
    path.write_text(condition_codes_as_json() + "\n")


if __name__ == "__main__":  # pragma: no cover
    write_condition_codes_json()
