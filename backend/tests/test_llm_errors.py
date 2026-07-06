import pytest

from skycast.llm.errors import LLMError, StructuredOutputError


def test_llm_error_can_be_raised_and_caught() -> None:
    with pytest.raises(LLMError):
        raise LLMError("transport failed")


def test_llm_error_carries_optional_reason() -> None:
    error = LLMError("transport failed", reason="timeout")
    assert str(error) == "transport failed"
    assert error.reason == "timeout"


def test_llm_error_reason_defaults_to_none() -> None:
    error = LLMError("transport failed")
    assert error.reason is None


def test_llm_error_is_a_plain_exception() -> None:
    assert issubclass(LLMError, Exception)


def test_structured_output_error_can_be_raised_and_caught() -> None:
    with pytest.raises(StructuredOutputError):
        raise StructuredOutputError("model could not produce valid output")


def test_structured_output_error_carries_optional_reason() -> None:
    error = StructuredOutputError(
        "model could not produce valid output", reason="repair_failed"
    )
    assert str(error) == "model could not produce valid output"
    assert error.reason == "repair_failed"


def test_structured_output_error_reason_defaults_to_none() -> None:
    error = StructuredOutputError("model could not produce valid output")
    assert error.reason is None


def test_structured_output_error_is_a_plain_exception() -> None:
    assert issubclass(StructuredOutputError, Exception)


def test_llm_error_and_structured_output_error_are_siblings_not_subclasses() -> None:
    assert not issubclass(StructuredOutputError, LLMError)
    assert not issubclass(LLMError, StructuredOutputError)
