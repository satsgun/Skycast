import pytest

from skycast.providers.errors import ProviderError


def test_provider_error_can_be_raised_and_caught() -> None:
    with pytest.raises(ProviderError):
        raise ProviderError("provider unreachable")


def test_provider_error_carries_optional_reason() -> None:
    error = ProviderError("provider unreachable", reason="connection timed out")
    assert str(error) == "provider unreachable"
    assert error.reason == "connection timed out"


def test_provider_error_reason_defaults_to_none() -> None:
    error = ProviderError("provider unreachable")
    assert error.reason is None


def test_provider_error_is_a_plain_exception() -> None:
    assert issubclass(ProviderError, Exception)
