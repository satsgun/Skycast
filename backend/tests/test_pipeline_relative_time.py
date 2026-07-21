from datetime import time

import pytest
from pydantic import ValidationError

from skycast.pipeline.relative_time import RelativeTimeKind, RelativeTimeSpec


def test_relative_time_kind_has_exactly_six_members() -> None:
    assert {member.value for member in RelativeTimeKind} == {
        "NOW",
        "TODAY",
        "THIS_EVENING",
        "TOMORROW",
        "NEXT_N_DAYS",
        "ABSOLUTE",
    }


@pytest.mark.parametrize(
    "kind",
    [
        RelativeTimeKind.NOW,
        RelativeTimeKind.TODAY,
        RelativeTimeKind.THIS_EVENING,
        RelativeTimeKind.TOMORROW,
    ],
)
def test_param_less_kinds_construct_without_extra_params(kind: RelativeTimeKind) -> None:
    spec = RelativeTimeSpec(kind=kind)
    assert spec.day_count is None
    assert spec.clock_time is None
    assert spec.day_offset == 0


def test_next_n_days_with_day_count_is_valid() -> None:
    spec = RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=3)
    assert spec.day_count == 3


def test_next_n_days_without_day_count_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS)


@pytest.mark.parametrize("day_count", [0, -1])
def test_next_n_days_day_count_must_be_positive(day_count: int) -> None:
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=day_count)


@pytest.mark.parametrize(
    "kind",
    [
        RelativeTimeKind.NOW,
        RelativeTimeKind.TODAY,
        RelativeTimeKind.THIS_EVENING,
        RelativeTimeKind.TOMORROW,
        RelativeTimeKind.ABSOLUTE,
    ],
)
def test_day_count_set_for_non_next_n_days_kind_is_rejected(kind: RelativeTimeKind) -> None:
    kwargs = {"clock_time": time(14, 0)} if kind == RelativeTimeKind.ABSOLUTE else {}
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind=kind, day_count=3, **kwargs)


def test_absolute_with_clock_time_is_valid() -> None:
    spec = RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0))
    assert spec.clock_time == time(14, 0)
    assert spec.day_offset == 0


def test_absolute_without_clock_time_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind=RelativeTimeKind.ABSOLUTE)


def test_absolute_day_offset_can_be_positive() -> None:
    spec = RelativeTimeSpec(
        kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0), day_offset=1
    )
    assert spec.day_offset == 1


def test_absolute_day_offset_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        RelativeTimeSpec(
            kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0), day_offset=-1
        )


@pytest.mark.parametrize(
    "kind",
    [
        RelativeTimeKind.NOW,
        RelativeTimeKind.TODAY,
        RelativeTimeKind.THIS_EVENING,
        RelativeTimeKind.TOMORROW,
        RelativeTimeKind.NEXT_N_DAYS,
    ],
)
def test_clock_time_set_for_non_absolute_kind_is_rejected(kind: RelativeTimeKind) -> None:
    kwargs = {"day_count": 3} if kind == RelativeTimeKind.NEXT_N_DAYS else {}
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind=kind, clock_time=time(14, 0), **kwargs)


@pytest.mark.parametrize(
    "kind",
    [
        RelativeTimeKind.NOW,
        RelativeTimeKind.TODAY,
        RelativeTimeKind.THIS_EVENING,
        RelativeTimeKind.TOMORROW,
        RelativeTimeKind.NEXT_N_DAYS,
    ],
)
def test_nonzero_day_offset_for_non_absolute_kind_is_rejected(kind: RelativeTimeKind) -> None:
    kwargs = {"day_count": 3} if kind == RelativeTimeKind.NEXT_N_DAYS else {}
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind=kind, day_offset=1, **kwargs)


def test_invalid_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RelativeTimeSpec(kind="NOT_A_REAL_KIND")


def test_spec_is_frozen() -> None:
    spec = RelativeTimeSpec(kind=RelativeTimeKind.TODAY)
    with pytest.raises(ValidationError):
        spec.kind = RelativeTimeKind.TOMORROW


def test_next_n_days_spec_round_trips_through_json() -> None:
    spec = RelativeTimeSpec(kind=RelativeTimeKind.NEXT_N_DAYS, day_count=3)
    assert RelativeTimeSpec.model_validate_json(spec.model_dump_json()) == spec


def test_absolute_spec_round_trips_through_json() -> None:
    spec = RelativeTimeSpec(
        kind=RelativeTimeKind.ABSOLUTE, clock_time=time(14, 0), day_offset=1
    )
    assert RelativeTimeSpec.model_validate_json(spec.model_dump_json()) == spec
