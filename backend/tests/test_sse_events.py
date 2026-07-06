from skycast.sse.events import SSEEventType

EXPECTED_MEMBERS_AND_VALUES = {
    "STEP": "step",
    "CLARIFY": "clarify",
    "ANSWER": "answer",
    "ERROR": "error",
}


def test_member_set_is_exactly_the_expected_four() -> None:
    assert [member.name for member in SSEEventType] == list(
        EXPECTED_MEMBERS_AND_VALUES
    )


def test_wire_values_are_lowercase_and_match_contract() -> None:
    for member in SSEEventType:
        assert member.value == EXPECTED_MEMBERS_AND_VALUES[member.name]


def test_round_trip_reconstructs_each_member() -> None:
    for member in SSEEventType:
        assert SSEEventType(member.value) is member


def test_is_a_str_subclass() -> None:
    assert isinstance(SSEEventType.STEP, str)
