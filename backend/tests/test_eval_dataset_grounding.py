"""Coverage for Task E4.5: the dataset's grounding wiring.

Uses the real pipeline (plan/execute) against the default InMemoryProvider
to learn each case's actual fixture facts (via derive_facts), rather than
hardcoding guessed fixture values -- same pattern as
eval/harness/deterministic.py and test_eval_stochastic_e2e.py.
"""

from __future__ import annotations

import asyncio

from skycast.llm.fake_client import FakeLLMClient
from skycast.pipeline.execute_stage import execute
from skycast.pipeline.plan_stage import plan
from skycast.pipeline.synthesis_output import SynthesisOutput
from skycast.providers.in_memory import InMemoryProvider

from eval.cases.dataset import _NOW, DATASET
from eval.harness.grounding import derive_facts
from eval.harness.stochastic import run_synthesize

_BY_ID = {c.id: c for c in DATASET}


async def _noop_emit(label, stage):
    return None


def _real_forecast(case_id: str):
    case = _BY_ID[case_id]
    providers = {"in-memory": InMemoryProvider()}
    tool_plan = plan(case.canned_spec, providers)
    result = asyncio.run(execute(tool_plan, providers, emit=_noop_emit, now=_NOW))
    return result.forecasts[0]


def _fake_llm(text: str) -> FakeLLMClient:
    def responder(*, system, user, schema, tool_name):
        return SynthesisOutput(text=text, highlight=None)

    return FakeLLMClient(responder)


def test_umbrella_decision_has_grounded_precip_factory() -> None:
    case = _BY_ID["umbrella_decision"]
    assert case.checks_synthesize_grounded is not None


def test_umbrella_decision_grounded_check_fails_when_answer_contradicts_real_fixture() -> None:
    facts = derive_facts(_real_forecast("umbrella_decision"))
    contradicting = (
        "No rain expected, it'll be dry and sunny." if facts.rain_likely
        else "Bring an umbrella, rain is likely this afternoon."
    )

    result = asyncio.run(run_synthesize(_BY_ID["umbrella_decision"], _fake_llm(contradicting)))

    grounded = next(c for c in result.checks if c.name == "answer_grounded_precip")
    assert not grounded.passed, grounded.detail


def test_umbrella_decision_grounded_check_passes_when_answer_is_silent_on_rain() -> None:
    result = asyncio.run(run_synthesize(_BY_ID["umbrella_decision"], _fake_llm("Have a nice day.")))

    grounded = next(c for c in result.checks if c.name == "answer_grounded_precip")
    assert grounded.passed, grounded.detail


def test_temperature_and_condition_grounded_cases_produce_both_check_names() -> None:
    for case_id in ("multiday_outlook", "simple_current", "decision_jacket"):
        case = _BY_ID[case_id]
        assert case.checks_synthesize_grounded is not None, case_id

        result = asyncio.run(run_synthesize(case, _fake_llm("A pleasant day overall.")))

        names = {c.name for c in result.checks}
        assert "answer_grounded_temperature" in names, case_id
        assert "answer_grounded_condition" in names, case_id


def test_cases_without_a_fitting_grounding_check_are_left_untouched() -> None:
    for case_id in (
        "decision_run_wind",
        "decision_sunscreen",
        "simple_reykjavik",
        "simple_paris",
        "outlook_weekend",
        "time_window_evening_resolved",
        "time_window_tomorrow_morning",
        "comparison_two_cities",
        "comparison_three_cities",
        "ambiguous_clarify",
        "ambiguous_portland",
        "not_found",
        "not_found_atlantis",
        "codegen_fallback_routing",
    ):
        assert _BY_ID[case_id].checks_synthesize_grounded is None, case_id


def test_comparison_resolvable_rubric_asks_about_faithfulness_to_the_forecasts() -> None:
    rubric = _BY_ID["comparison_resolvable"].judge_rubric
    assert rubric is not None
    assert "consistent" in rubric.lower()
    assert "temperature" in rubric.lower()
