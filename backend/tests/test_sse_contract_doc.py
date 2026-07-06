from skycast.sse.contract_doc import (
    DEFAULT_DOC_PATH,
    clarify_path_events,
    happy_path_events,
    render_example_stream,
    render_sse_contract_doc,
    write_sse_contract_doc,
)
from skycast.sse.envelope import SSEEvent
from skycast.sse.events import SSEEventType


def _event_types_in(stream: str) -> list[SSEEventType]:
    data_lines = [line for line in stream.split("\n") if line.startswith("data: ")]
    events = [
        SSEEvent.model_validate_json(line.removeprefix("data: "))
        for line in data_lines
    ]
    return [event.type for event in events]


def test_render_contains_envelope_shape_section() -> None:
    doc = render_sse_contract_doc()
    assert "## Envelope shape" in doc
    assert '"type"' in doc and '"data"' in doc


def test_render_mentions_all_four_event_types() -> None:
    doc = render_sse_contract_doc()
    for event_type in ("step", "clarify", "answer", "error"):
        assert f"`{event_type}`" in doc


def test_render_contains_ordering_invariant() -> None:
    doc = render_sse_contract_doc()
    assert "## Ordering invariant" in doc
    assert "exactly one terminal event" in doc


def test_happy_path_example_is_zero_or_more_steps_then_one_answer() -> None:
    stream = render_example_stream(happy_path_events())
    types = _event_types_in(stream)
    assert types[-1] is SSEEventType.ANSWER
    assert all(t is SSEEventType.STEP for t in types[:-1])


def test_clarify_path_example_is_zero_or_more_steps_then_one_clarify() -> None:
    stream = render_example_stream(clarify_path_events())
    types = _event_types_in(stream)
    assert types[-1] is SSEEventType.CLARIFY
    assert all(t is SSEEventType.STEP for t in types[:-1])


def test_rendered_doc_embeds_the_same_example_streams() -> None:
    doc = render_sse_contract_doc()
    assert render_example_stream(happy_path_events()) in doc
    assert render_example_stream(clarify_path_events()) in doc


def test_write_sse_contract_doc_writes_matching_content(tmp_path) -> None:
    output_path = tmp_path / "sse-contract.md"
    write_sse_contract_doc(output_path)
    assert output_path.read_text(encoding="utf-8") == render_sse_contract_doc()


def test_committed_doc_matches_current_generation() -> None:
    assert DEFAULT_DOC_PATH.read_text(encoding="utf-8") == render_sse_contract_doc()
