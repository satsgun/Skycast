import json

import pytest
from pydantic import ValidationError

from skycast.domain.location import Location


def test_can_be_constructed_with_only_required_fields() -> None:
    location = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6)
    assert location.country is None
    assert location.country_code is None
    assert location.admin1 is None
    assert location.admin2 is None
    assert location.population is None
    assert location.timezone is None


def test_missing_coordinates_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        Location(id="1", name="Springfield")


def test_dict_round_trip_minimal() -> None:
    location = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6)
    restored = Location(**location.model_dump())
    assert restored == location


def test_dict_round_trip_fully_populated() -> None:
    location = Location(
        id="1",
        name="Springfield",
        latitude=39.8,
        longitude=-89.6,
        country="United States",
        country_code="US",
        admin1="Illinois",
        admin2="Sangamon",
        population=114230,
        timezone="America/Chicago",
    )
    restored = Location(**location.model_dump())
    assert restored == location


def test_json_round_trip_minimal() -> None:
    location = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6)
    restored = Location.model_validate_json(location.model_dump_json())
    assert restored == location


def test_json_round_trip_fully_populated() -> None:
    location = Location(
        id="1",
        name="Springfield",
        latitude=39.8,
        longitude=-89.6,
        country="United States",
        country_code="US",
        admin1="Illinois",
        admin2="Sangamon",
        population=114230,
        timezone="America/Chicago",
    )
    restored = Location.model_validate_json(location.model_dump_json())
    assert restored == location


def test_list_of_locations_round_trips_through_json() -> None:
    candidates = [
        Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6, admin1="Illinois"),
        Location(id="2", name="Springfield", latitude=37.2, longitude=-93.3, admin1="Missouri"),
    ]
    payload = json.dumps([location.model_dump(mode="json") for location in candidates])
    restored = [Location(**data) for data in json.loads(payload)]
    assert restored == candidates


def test_location_can_be_looked_up_by_id_among_candidates() -> None:
    first = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6, admin1="Illinois")
    second = Location(id="2", name="Springfield", latitude=37.2, longitude=-93.3, admin1="Missouri")
    candidates = [first, second]

    found = next(candidate for candidate in candidates if candidate.id == "2")

    assert found is second


def test_field_identical_locations_are_equal_and_hash_equal() -> None:
    first = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6, admin1="Illinois")
    second = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6, admin1="Illinois")

    assert first == second
    assert hash(first) == hash(second)


def test_frozen_instance_rejects_mutation() -> None:
    location = Location(id="1", name="Springfield", latitude=39.8, longitude=-89.6)
    with pytest.raises(ValidationError):
        location.name = "Shelbyville"
