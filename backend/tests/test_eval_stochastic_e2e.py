"""Regression coverage for eval-harness bug: run_end_to_end() never wired
a default location into QueryRequest, so a location-less query could
never reach its expected `answer` terminal event even when the rest of
the pipeline behaved correctly -- plan() has nowhere to resolve a target
from without one. Drives the real run_query() generator end to end with
a FakeLLMClient (no network) so the fix is verified against actual
pipeline behavior, not a mock of it.
"""

from __future__ import annotations

from skycast.domain.location import Location
from skycast.domain.provider import Granularity, WeatherVariable
from skycast.llm.fake_client import FakeLLMClient
from skycast.pipeline.data_needs import DataNeedsSpec, QueryIntent
from skycast.pipeline.synthesis_output import SynthesisOutput

from eval.cases.dataset import DATASET
from eval.harness import checks as C
from eval.harness.stochastic import run_end_to_end, run_synthesize
from eval.harness.types import Check, EvalCase

_LOCATION = Location(
    id="in-memory:hyderabad-in",
    name="Hyderabad",
    latitude=17.385,
    longitude=78.4867,
    country="India",
    country_code="IN",
    admin1="Telangana",
    population=6809970,
    timezone="Asia/Kolkata",
)

_NO_LOCATION_SPEC = DataNeedsSpec(
    location_names=[],
    granularities={Granularity.CURRENT},
    variables={WeatherVariable.PRECIP_PROBABILITY},
    intent=QueryIntent.CONDITIONS,
)


def _fake_llm() -> FakeLLMClient:
    def responder(*, system, user, schema, tool_name):
        if schema is DataNeedsSpec:
            return _NO_LOCATION_SPEC
        return SynthesisOutput(text="It looks clear right now.", highlight=None)

    return FakeLLMClient(responder)


def _case(*, default_location: Location | None) -> EvalCase:
    return EvalCase(
        id="no_location_default",
        query="Will it rain today?",
        expect_terminal="answer",
        default_location=default_location,
    )


def test_run_end_to_end_resolves_default_location_for_a_location_less_query() -> None:
    result = run_end_to_end(_case(default_location=_LOCATION), _fake_llm())

    assert result.error is None
    terminal_check = result.checks[0]
    assert terminal_check.passed, terminal_check.detail


def test_run_end_to_end_errors_without_a_default_location() -> None:
    """Contrast case: confirms the fix is precise -- a case that genuinely
    has no default location still surfaces as a real failure, not masked.
    """
    result = run_end_to_end(_case(default_location=None), _fake_llm())

    assert result.error is None
    terminal_check = result.checks[0]
    assert not terminal_check.passed
    assert "terminal=error" in terminal_check.detail


def test_dataset_default_location_cases_carry_a_default_location() -> None:
    by_id = {c.id: c for c in DATASET}
    for case_id in ("no_location_default", "default_should_i_go_out"):
        assert by_id[case_id].default_location is not None, case_id


# --- checks_synthesize_grounded wiring (Task E4.4) ---

_HYDERABAD_SPEC = DataNeedsSpec(
    location_names=["Hyderabad"],
    granularities={Granularity.CURRENT},
    variables={WeatherVariable.PRECIP_PROBABILITY},
    intent=QueryIntent.CONDITIONS,
)


def _synthesize_fake_llm() -> FakeLLMClient:
    def responder(*, system, user, schema, tool_name):
        return SynthesisOutput(text="It looks clear right now.", highlight=None)

    return FakeLLMClient(responder)


def _grounded_case(*, grounded) -> EvalCase:
    return EvalCase(
        id="synthesize_grounded_wiring",
        query="Will it rain in Hyderabad?",
        canned_spec=_HYDERABAD_SPEC,
        checks_synthesize=(C.answer_nonempty(),),
        checks_synthesize_grounded=grounded,
    )


def test_run_synthesize_invokes_grounded_factory_with_the_real_execute_forecasts() -> None:
    """The factory must see the actual Forecast execute() produced (from
    InMemoryProvider's real Hyderabad fixture) -- not a stand-in the case
    hand-authored -- otherwise a grounding check built from it could drift
    from what the pipeline actually returns.
    """
    captured: list = []

    def grounded(forecasts):
        captured.append(forecasts)
        saw_hyderabad = forecasts[0].location.name == "Hyderabad"
        return (Check("saw_hyderabad", lambda answer: (saw_hyderabad, "ok")),)

    result = run_synthesize(_grounded_case(grounded=grounded), _synthesize_fake_llm())

    assert result.error is None
    assert len(captured) == 1
    assert captured[0][0].location.name == "Hyderabad"
    names = [c.name for c in result.checks]
    assert names == ["answer_nonempty", "saw_hyderabad"]
    saw_hyderabad = next(c for c in result.checks if c.name == "saw_hyderabad")
    assert saw_hyderabad.passed, saw_hyderabad.detail


def test_run_synthesize_without_grounded_factory_behaves_as_before() -> None:
    result = run_synthesize(_grounded_case(grounded=None), _synthesize_fake_llm())

    assert result.error is None
    assert [c.name for c in result.checks] == ["answer_nonempty"]
