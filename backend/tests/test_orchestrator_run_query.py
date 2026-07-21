import asyncio
from datetime import datetime, timezone

from skycast.api.query_request import QueryRequest
from skycast.domain.forecast import Forecast
from skycast.domain.location import Location
from skycast.domain.provider import ForecastRequest, Granularity, ProviderCapabilities, WeatherVariable
from skycast.llm.errors import LLMError, StructuredOutputError
from skycast.llm.fake_client import FakeLLMClient
from skycast.orchestrator.run_query import _stream_execute, run_query
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.execute_result import Success
from skycast.pipeline.plan_stage import plan
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.providers.base import WeatherProvider
from skycast.providers.in_memory import InMemoryProvider
from skycast.sse.events import SSEEventType
from skycast.sse.payloads import ErrorKind, ForecastBlock, Highlight, PipelineStage, ReadingLocator


def _run(coro):
    return asyncio.run(coro)


async def _collect(agen) -> list:
    return [event async for event in agen]


def _now() -> datetime:
    return datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def _hyderabad() -> Location:
    return Location(
        id="in-memory:hyderabad-in", name="Hyderabad", latitude=17.385, longitude=78.4867,
        country="India", country_code="IN", timezone="Asia/Kolkata",
    )


def _springfield_il() -> Location:
    return Location(
        id="in-memory:springfield-il-us", name="Springfield", latitude=39.7817, longitude=-89.6501,
        country="United States", country_code="US", admin1="Illinois", population=114230,
        timezone="America/Chicago",
    )


def _austin() -> Location:
    return Location(
        id="test:austin", name="Austin", latitude=30.2672, longitude=-97.7431, timezone="America/Chicago"
    )


def _dallas() -> Location:
    return Location(
        id="test:dallas", name="Dallas", latitude=32.7767, longitude=-96.7970, timezone="America/Chicago"
    )


def _request(query: str = "Do I need an umbrella?", **overrides) -> QueryRequest:
    return QueryRequest(query=query, now=_now(), **overrides)


def _spec(**overrides) -> DataNeedsSpec:
    defaults = dict(
        location_names=["Hyderabad"],
        granularities={Granularity.CURRENT},
        variables={WeatherVariable.TEMPERATURE},
        intent=QueryIntent.DECISION,
    )
    defaults.update(overrides)
    return DataNeedsSpec(**defaults)


def _synthesis_output(**overrides) -> SynthesisOutput:
    defaults = dict(text="Yes, bring an umbrella.", highlight=None)
    defaults.update(overrides)
    return SynthesisOutput(**defaults)


def _llm_client(decompose_outcome, synthesize_outcome=None, call_log: list[str] | None = None):
    log = call_log if call_log is not None else []

    def responder(*, system, user, schema, tool_name):
        log.append(tool_name)
        if tool_name == "emit_data_needs":
            return decompose_outcome
        return synthesize_outcome if synthesize_outcome is not None else _synthesis_output()

    return FakeLLMClient(responder)


def _assert_terminal_invariant(events: list) -> None:
    terminal_types = {SSEEventType.ANSWER, SSEEventType.CLARIFY, SSEEventType.ERROR}
    assert len(events) >= 1
    assert events[-1].type in terminal_types
    assert all(e.type is SSEEventType.STEP for e in events[:-1])
    assert sum(1 for e in events if e.type in terminal_types) == 1


def _full_capabilities() -> ProviderCapabilities:
    return ProviderCapabilities(
        max_forecast_days=16, available_variables=set(WeatherVariable), supports_geocoding=True
    )


class _GeocodeSpyProvider(InMemoryProvider):
    async def geocode(self, name: str) -> list[Location]:
        raise AssertionError("geocode must not be called for a name already in resolved_locations")


class _BuggyForecastProvider(WeatherProvider):
    async def geocode(self, name: str) -> list[Location]:
        raise AssertionError("not used -- coords-known chain")

    async def fetch_forecast(self, location: Location, request: ForecastRequest) -> Forecast:
        raise RuntimeError("unexpected bug in provider")

    def capabilities(self) -> ProviderCapabilities:
        return _full_capabilities()


class _HangingProvider(WeatherProvider):
    def __init__(self) -> None:
        self.fetch_started = asyncio.Event()
        self.cancelled = False

    async def geocode(self, name: str) -> list[Location]:
        raise AssertionError("not used -- coords-known chain")

    async def fetch_forecast(self, location: Location, request: ForecastRequest) -> Forecast:
        self.fetch_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    def capabilities(self) -> ProviderCapabilities:
        return _full_capabilities()


def test_happy_path_single_named_location() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Hyderabad"]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ANSWER
    stages = [e.data.stage for e in events if e.type is SSEEventType.STEP]
    assert stages == [
        PipelineStage.DECOMPOSE,
        PipelineStage.PLAN,
        PipelineStage.EXECUTE_GEOCODE,
        PipelineStage.EXECUTE_FORECAST,
        PipelineStage.SYNTHESIZE,
    ]
    assert events[-1].data.card.forecasts[0].location.name == "Hyderabad"


def test_clarify_path_ambiguous_location() -> None:
    request = _request(query="What's the weather in Springfield?")
    providers = {"in-memory": InMemoryProvider()}
    call_log: list[str] = []
    llm = _llm_client(_spec(location_names=["Springfield"]), call_log=call_log)

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.CLARIFY
    assert len(events[-1].data.candidates) == 3
    assert events[-1].data.for_location_name == "Springfield"
    assert events[-1].data.resolved == {}
    assert call_log == ["emit_data_needs"]


def test_disambiguation_requery_when_spec_already_has_no_location_name() -> None:
    request = _request(
        query="What's the weather there?",
        resolved_locations={"Springfield": _springfield_il()},
    )
    providers = {"in-memory": _GeocodeSpyProvider()}
    llm = _llm_client(_spec(location_names=[]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ANSWER
    assert events[-1].data.card.forecasts[0].location.name == "Springfield"


def test_disambiguation_requery_overrides_named_location_and_skips_geocode() -> None:
    request = _request(
        query="What's the weather in Springfield?",
        resolved_locations={"Springfield": _springfield_il()},
    )
    providers = {"in-memory": _GeocodeSpyProvider()}
    llm = _llm_client(_spec(location_names=["Springfield"]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ANSWER
    assert events[-1].data.card.forecasts[0].location.admin1 == "Illinois"


def test_comparison_one_ambiguous_one_resolved_carries_resolved_sibling_forward() -> None:
    """The central regression test for fix #90: round 1's clarify must
    not drop Mumbai just because Delhi needs disambiguation, and round
    2's re-query (carrying both the resolved sibling and the newly
    -picked candidate) must complete the comparison with both forecasts
    -- and must not re-geocode either name.
    """
    mumbai = Location(
        id="in-memory:mumbai-in", name="Mumbai", latitude=19.0760, longitude=72.8777,
        country="India", country_code="IN", timezone="Asia/Kolkata",
    )
    delhi = Location(
        id="in-memory:delhi-in", name="Delhi", latitude=28.65, longitude=77.23,
        country="India", country_code="IN", admin1="Delhi", timezone="Asia/Kolkata",
    )
    delhi_us = Location(
        id="in-memory:delhi-us", name="Delhi", latitude=42.27, longitude=-74.91,
        country="United States", country_code="US", admin1="New York", timezone="America/New_York",
    )
    providers = {
        "in-memory": InMemoryProvider(
            locations={"mumbai": [mumbai], "delhi": [delhi, delhi_us]}
        )
    }
    llm = _llm_client(_spec(location_names=["Mumbai", "Delhi"], intent=QueryIntent.COMPARISON))

    round1 = _run(
        _collect(
            run_query(
                _request(query="Compare the weather in Mumbai and Delhi"), providers, llm
            )
        )
    )

    _assert_terminal_invariant(round1)
    assert round1[-1].type is SSEEventType.CLARIFY
    assert round1[-1].data.for_location_name == "Delhi"
    assert round1[-1].data.resolved == {"Mumbai": mumbai}

    round2_providers = {"in-memory": _GeocodeSpyProvider()}
    round2_request = _request(
        query="Compare the weather in Mumbai and Delhi",
        resolved_locations={**round1[-1].data.resolved, "Delhi": delhi},
    )
    round2 = _run(_collect(run_query(round2_request, round2_providers, llm)))

    _assert_terminal_invariant(round2)
    assert round2[-1].type is SSEEventType.ANSWER
    forecasts = round2[-1].data.card.forecasts
    assert [f.location.name for f in forecasts] == ["Mumbai", "Delhi"]
    assert forecasts[1].location.admin1 == "Delhi"


def test_decompose_naming_the_default_location_still_resolves_directly() -> None:
    # Fix #94: decompose is instructed to leave location_names empty when
    # a default location covers the query, but isn't always reliable
    # about it (confirmed live against the deployed Gemini-backed
    # backend). Simulates exactly that buggy output -- the pipeline must
    # still resolve directly via default_location, not re-geocode the
    # name and risk the exact worldwide ambiguity default_location exists
    # to avoid.
    request = _request(query="weather this evening", default_location=_hyderabad())
    providers = {"in-memory": _GeocodeSpyProvider()}
    llm = _llm_client(_spec(location_names=["Hyderabad"]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ANSWER
    assert events[-1].data.card.forecasts[0].location.name == "Hyderabad"


def test_not_found_location_maps_to_not_found_error() -> None:
    request = _request(query="What's the weather in Nowhereville?")
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Nowhereville"]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.NOT_FOUND


def test_provider_outage_maps_to_provider_unreachable_error() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider(fail_forecast=True)}
    llm = _llm_client(_spec(location_names=["Hyderabad"]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.PROVIDER_UNREACHABLE


def test_no_location_named_and_no_default_maps_to_bad_input() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=[]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.BAD_INPUT


def test_llm_error_at_decompose_maps_to_provider_unreachable() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(LLMError("timeout"))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.PROVIDER_UNREACHABLE
    assert len(events) == 2


def test_structured_output_error_at_decompose_maps_to_internal() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(StructuredOutputError("bad schema"))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.INTERNAL


def test_llm_error_at_synthesize_maps_to_provider_unreachable() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(_spec(location_names=["Hyderabad"]), synthesize_outcome=LLMError("timeout"))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.PROVIDER_UNREACHABLE


def test_structured_output_error_at_synthesize_maps_to_internal() -> None:
    request = _request()
    providers = {"in-memory": InMemoryProvider()}
    llm = _llm_client(
        _spec(location_names=["Hyderabad"]), synthesize_outcome=StructuredOutputError("bad")
    )

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.INTERNAL


def test_comparison_happy_path_card_carries_both_forecasts_in_order() -> None:
    request = _request(query="Is it warmer in Austin or Dallas?")
    providers = {
        "in-memory": InMemoryProvider(locations={"austin": [_austin()], "dallas": [_dallas()]})
    }
    highlight = Highlight(forecast_index=1, locator=ReadingLocator(block=ForecastBlock.CURRENT))
    llm = _llm_client(
        _spec(location_names=["Austin", "Dallas"], intent=QueryIntent.COMPARISON),
        synthesize_outcome=_synthesis_output(text="Dallas is warmer.", highlight=highlight),
    )

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ANSWER
    forecasts = events[-1].data.card.forecasts
    assert [f.location.name for f in forecasts] == ["Austin", "Dallas"]
    assert events[-1].data.text == "Dallas is warmer."


def test_unexpected_exception_is_caught_by_top_level_guard() -> None:
    request = _request(default_location=_hyderabad())
    providers = {"in-memory": _BuggyForecastProvider()}
    llm = _llm_client(_spec(location_names=[]))

    events = _run(_collect(run_query(request, providers, llm)))

    _assert_terminal_invariant(events)
    assert events[-1].type is SSEEventType.ERROR
    assert events[-1].data.kind is ErrorKind.INTERNAL


def test_stream_execute_yields_steps_before_populating_result_box() -> None:
    spec = _spec(location_names=["Hyderabad"])
    providers = {"in-memory": InMemoryProvider()}
    built_plan = plan(spec, providers)
    result_box: list = []

    async def drive():
        events = []
        async for event in _stream_execute(built_plan, providers, result_box, now=_now()):
            assert result_box == []
            events.append(event)
        return events

    events = _run(drive())

    assert len(events) >= 1
    assert all(e.type is SSEEventType.STEP for e in events)
    assert len(result_box) == 1
    assert isinstance(result_box[0], Success)


def test_stream_execute_cancels_execute_task_on_early_generator_close() -> None:
    spec = _spec(location_names=[])
    provider = _HangingProvider()
    providers = {"in-memory": provider}
    built_plan = plan(spec, providers, default_location=_hyderabad())
    result_box: list = []

    async def drive():
        gen = _stream_execute(built_plan, providers, result_box, now=_now())
        await gen.__anext__()
        await provider.fetch_started.wait()
        await gen.aclose()

    _run(drive())

    assert provider.cancelled is True
