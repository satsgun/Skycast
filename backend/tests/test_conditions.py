import json
from pathlib import Path

import skycast.domain.conditions as conditions_module
from skycast.domain.conditions import ConditionCode, condition_codes_as_json, write_condition_codes_json

EXPECTED_MEMBERS = [
    "CLEAR",
    "MAINLY_CLEAR",
    "PARTLY_CLOUDY",
    "CLOUDY",
    "FOG",
    "DRIZZLE",
    "FREEZING_DRIZZLE",
    "RAIN",
    "HEAVY_RAIN",
    "FREEZING_RAIN",
    "SNOW",
    "HEAVY_SNOW",
    "RAIN_SHOWERS",
    "SNOW_SHOWERS",
    "THUNDERSTORM",
    "UNKNOWN",
]


def test_every_member_value_equals_its_name() -> None:
    for member in ConditionCode:
        assert member.value == member.name


def test_member_set_is_exactly_the_expected_sixteen() -> None:
    assert [member.name for member in ConditionCode] == EXPECTED_MEMBERS


def test_unknown_is_present() -> None:
    assert ConditionCode.UNKNOWN.value == "UNKNOWN"


def test_json_export_matches_declaration_order_and_content() -> None:
    exported = json.loads(condition_codes_as_json())
    assert exported == [member.value for member in ConditionCode]
    assert exported == EXPECTED_MEMBERS


def test_round_trip_reconstructs_each_member() -> None:
    for member in ConditionCode:
        assert ConditionCode(member.value) is member


def test_write_condition_codes_json_writes_matching_content(tmp_path: Path) -> None:
    output_path = tmp_path / "conditions.json"
    write_condition_codes_json(output_path)
    assert output_path.read_text() == condition_codes_as_json() + "\n"


def test_committed_json_file_matches_export() -> None:
    committed_path = Path(conditions_module.__file__).parent / "conditions.json"
    assert committed_path.read_text() == condition_codes_as_json() + "\n"
