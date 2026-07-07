import pytest

from skycast.pipeline.errors import NoCapableProviderError, NoLocationError


def test_no_capable_provider_error_can_be_raised_and_caught() -> None:
    with pytest.raises(NoCapableProviderError):
        raise NoCapableProviderError("no provider satisfies the request")


def test_no_capable_provider_error_carries_optional_reason() -> None:
    error = NoCapableProviderError(
        "no provider satisfies the request", reason="missing_variables"
    )
    assert str(error) == "no provider satisfies the request"
    assert error.reason == "missing_variables"


def test_no_capable_provider_error_reason_defaults_to_none() -> None:
    error = NoCapableProviderError("no provider satisfies the request")
    assert error.reason is None


def test_no_capable_provider_error_is_a_plain_exception() -> None:
    assert issubclass(NoCapableProviderError, Exception)


def test_no_location_error_can_be_raised_and_caught() -> None:
    with pytest.raises(NoLocationError):
        raise NoLocationError("no location named and no default configured")


def test_no_location_error_carries_optional_reason() -> None:
    error = NoLocationError(
        "no location named and no default configured",
        reason="no_location_and_no_default",
    )
    assert str(error) == "no location named and no default configured"
    assert error.reason == "no_location_and_no_default"


def test_no_location_error_reason_defaults_to_none() -> None:
    error = NoLocationError("no location named and no default configured")
    assert error.reason is None


def test_no_location_error_is_a_plain_exception() -> None:
    assert issubclass(NoLocationError, Exception)
