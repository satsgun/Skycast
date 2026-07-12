from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from skycast.api.routes import get_llm_client, get_providers
from skycast.domain.provider import Granularity, WeatherVariable
from skycast.llm.fake_client import FakeLLMClient
from skycast.main import app
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.providers.in_memory import InMemoryProvider
from skycast.sse.envelope import SSEEvent
from skycast.sse.events import SSEEventType

client = TestClient(app)


@pytest.fixture
def override_deps():
    def _override(providers, llm) -> None:
        app.dependency_overrides[get_providers] = lambda: providers
        app.dependency_overrides[get_llm_client] = lambda: llm

    yield _override
    app.dependency_overrides.clear()


def _now() -> datetime:
    return datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _request_body(**overrides) -> dict:
    body = {"query": "Do I need an umbrella?", "now": _now().isoformat()}
    body.update(overrides)
    return body


def _spec(**overrides) -> DataNeedsSpec:
    defaults = dict(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.DECISION,
    )
    defaults.update(overrides)
    return DataNeedsSpec(**defaults)


def _llm_client(decompose_outcome, synthesize_outcome=None):
    def responder(*, system, user, schema, tool_name):
        if tool_name == "emit_data_needs":
            return decompose_outcome
        if synthesize_outcome is not None:
            return synthesize_outcome
        return SynthesisOutput(text="Yes, bring an umbrella.", highlight=None)

    return FakeLLMClient(responder)


def _parse_events(text: str) -> list[SSEEvent]:
    blocks = [b for b in text.split("\n\n") if b.strip()]
    events = []
    for block in blocks:
        line = block.strip()
        assert line.startswith("data: ")
        events.append(SSEEvent.model_validate_json(line.removeprefix("data: ")))
    return events


def test_happy_path_streams_steps_then_answer(override_deps) -> None:
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Hyderabad"]))
    override_deps(providers, llm)

    response = client.post("/query", json=_request_body())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = _parse_events(response.text)
    assert events[-1].type is SSEEventType.ANSWER
    assert all(e.type is SSEEventType.STEP for e in events[:-1])


def test_clarify_path_streams_clarify_event(override_deps) -> None:
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Springfield"]))
    override_deps(providers, llm)

    response = client.post("/query", json=_request_body(query="What's the weather in Springfield?"))

    events = _parse_events(response.text)
    assert events[-1].type is SSEEventType.CLARIFY
    assert len(events[-1].data.candidates) == 3
    assert events[-1].data.for_location_name == "Springfield"


def test_not_found_streams_error_event(override_deps) -> None:
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Nowhereville"]))
    override_deps(providers, llm)

    response = client.post(
        "/query", json=_request_body(query="What's the weather in Nowhereville?")
    )

    events = _parse_events(response.text)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind == "not_found"


def test_missing_dependency_override_fails_loudly() -> None:
    app.dependency_overrides.clear()
    # The shared `client` re-raises server exceptions (useful for the
    # other tests); a real deployed server would instead return a plain
    # 500 -- assert that production-facing behavior here specifically.
    unraising_client = TestClient(app, raise_server_exceptions=False)

    response = unraising_client.post("/query", json=_request_body())

    assert response.status_code == 500


def test_missing_llm_override_alone_fails_loudly() -> None:
    app.dependency_overrides.clear()
    app.dependency_overrides[get_providers] = lambda: {"in-memory": InMemoryProvider()}
    unraising_client = TestClient(app, raise_server_exceptions=False)

    response = unraising_client.post("/query", json=_request_body())

    app.dependency_overrides.clear()
    assert response.status_code == 500


def test_malformed_request_body_returns_422(override_deps) -> None:
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec())
    override_deps(providers, llm)

    response = client.post("/query", json={"now": _now().isoformat()})

    assert response.status_code == 422


def test_cors_headers_present_for_allowed_origin(override_deps) -> None:
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Hyderabad"]))
    override_deps(providers, llm)

    response = client.post(
        "/query", json=_request_body(), headers={"Origin": "http://localhost:5173"}
    )

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_succeeds_for_allowed_origin() -> None:
    response = client.options(
        "/query",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "POST" in response.headers["access-control-allow-methods"]


def test_get_providers_reads_from_app_state_when_not_overridden() -> None:
    app.dependency_overrides.clear()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Hyderabad"]))
    app.state.providers = providers
    app.state.llm_client = llm
    try:
        response = client.post("/query", json=_request_body())
        assert response.status_code == 200
    finally:
        del app.state.providers
        del app.state.llm_client


def test_lifespan_wires_real_providers_and_llm_client_into_app_state() -> None:
    try:
        with TestClient(app) as temp_client:
            assert isinstance(app.state.providers, dict)
            assert "in-memory" in app.state.providers
            assert app.state.llm_client is not None
            response = temp_client.get("/health")
            assert response.status_code == 200
    finally:
        del app.state.providers
        del app.state.llm_client
