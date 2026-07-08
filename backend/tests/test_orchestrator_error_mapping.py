from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.orchestrator.error_mapping import map_error
from skycast.pipeline.errors import NoCapableProviderError, NoLocationError
from skycast.sse.payloads import ErrorKind


def test_no_location_error_maps_to_bad_input() -> None:
    payload = map_error(NoLocationError("no location"))

    assert payload.kind is ErrorKind.BAD_INPUT
    assert payload.message == "no location"


def test_no_capable_provider_error_maps_to_internal() -> None:
    error = NoCapableProviderError("no provider", reason="missing_variables")

    payload = map_error(error)

    assert payload.kind is ErrorKind.INTERNAL
    assert payload.message == "no provider"


def test_structured_output_error_maps_to_internal() -> None:
    payload = map_error(StructuredOutputError("bad schema"))

    assert payload.kind is ErrorKind.INTERNAL
    assert payload.message == "bad schema"


def test_llm_error_maps_to_provider_unreachable() -> None:
    error = LLMError("timeout", reason="timeout")

    payload = map_error(error)

    assert payload.kind is ErrorKind.PROVIDER_UNREACHABLE
    assert payload.message == "timeout"


def test_arbitrary_value_error_maps_to_internal_with_generic_message() -> None:
    payload = map_error(ValueError("some internal detail"))

    assert payload.kind is ErrorKind.INTERNAL
    assert payload.message != "some internal detail"
    assert "internal detail" not in payload.message


def test_arbitrary_key_error_maps_to_internal_with_generic_message() -> None:
    payload = map_error(KeyError("secret_key"))

    assert payload.kind is ErrorKind.INTERNAL
    assert "secret_key" not in payload.message


def test_arbitrary_runtime_error_maps_to_internal_with_generic_message() -> None:
    payload = map_error(RuntimeError("boom"))

    assert payload.kind is ErrorKind.INTERNAL
    assert payload.message != "boom"


def test_determinism_same_exception_produces_equal_payload() -> None:
    error = LLMError("timeout")

    first = map_error(error)
    second = map_error(error)

    assert first == second
