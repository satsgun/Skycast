"""Coverage for eval.harness.baseline -- previously had none.

Adds a "model" field to build_baseline's output so a saved baseline is
self-describing about which vendor/model produced its scores. Without
it, --baseline diffing (meant to catch drift on the SAME model) can't be
told apart from a comparison across two DIFFERENT models -- a score
change would look identical either way.
"""

from __future__ import annotations

from eval.harness.aggregate import AggregateReport, StageAggregate
from eval.harness.baseline import (
    build_baseline,
    diff_against_baseline,
    load_baseline,
    save_baseline,
)
from eval.harness.types import Stage, Tier
from skycast.llm.usage import Usage


def _stage_aggregate(stage: Stage, *, passed: bool = True) -> StageAggregate:
    agg = StageAggregate(case_id="case_a", stage=stage, tier=Tier.STOCHASTIC, runs=1)
    agg.observe("check_a", passed, "detail")
    return agg


def test_build_baseline_includes_model_from_usages() -> None:
    report = AggregateReport()
    report.add(_stage_aggregate(Stage.DECOMPOSE))
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=10, output_tokens=5, model="gemini-3.5-flash")
    ]

    result = build_baseline(report)

    assert result["model"] == "gemini-3.5-flash"


def test_build_baseline_model_is_none_without_usages() -> None:
    report = AggregateReport()
    report.add(StageAggregate(case_id="case_a", stage=Stage.PLAN, tier=Tier.DETERMINISTIC, runs=1))
    report.stages[0].observe("check_a", True, "detail")

    result = build_baseline(report)

    assert result["model"] is None


def test_save_and_load_baseline_roundtrip_preserves_model(tmp_path) -> None:
    report = AggregateReport()
    report.add(_stage_aggregate(Stage.DECOMPOSE))
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=10, output_tokens=5, model="gemini-3.5-flash")
    ]
    path = tmp_path / "baseline.json"

    save_baseline(report, str(path))
    loaded = load_baseline(str(path))

    assert loaded["model"] == "gemini-3.5-flash"


def test_diff_against_baseline_ignores_model_field() -> None:
    baseline_report = AggregateReport()
    baseline_report.add(_stage_aggregate(Stage.DECOMPOSE, passed=True))
    baseline_report.usages["case_a::decompose"] = [
        Usage(input_tokens=10, output_tokens=5, model="gemini-3.5-flash")
    ]
    baseline = build_baseline(baseline_report)

    current_report = AggregateReport()
    current_report.add(_stage_aggregate(Stage.DECOMPOSE, passed=False))
    current_report.usages["case_a::decompose"] = [
        Usage(input_tokens=10, output_tokens=5, model="claude-sonnet-4-5")
    ]

    regressions = diff_against_baseline(current_report, baseline)

    assert len(regressions) == 1
    reg = regressions[0]
    assert reg.stage == "decompose"
    assert reg.baseline == 1.0
    assert reg.current == 0.0
    assert reg.flagged is True
