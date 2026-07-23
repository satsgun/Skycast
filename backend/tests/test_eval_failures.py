"""Coverage for eval.harness.failures -- a --save-failures artifact that
persists which checks failed, on which cases, with what detail, as JSON.

print_variance (eval/harness/report.py) already prints this, but only to
the terminal and only one truncated failing-detail sample per check.
This captures the full picture (every failing run's detail, not just
one) so it survives past the terminal session -- needed to target a
prompt edit at an actual observed failure pattern, and to diff two runs'
failures against each other afterward.
"""

from __future__ import annotations

import json

from eval.harness.aggregate import AggregateReport, StageAggregate
from eval.harness.failures import build_failure_report, save_failure_report
from eval.harness.types import Stage, Tier
from skycast.llm.usage import Usage


def test_build_failure_report_includes_failing_checks_with_all_details() -> None:
    report = AggregateReport()
    agg = StageAggregate(case_id="case_a", stage=Stage.DECOMPOSE, tier=Tier.STOCHASTIC, runs=3)
    agg.observe("variable_recall", True, "ok")
    agg.observe("variable_recall", False, "missing wind_speed")
    agg.observe("variable_recall", True, "ok")
    report.add(agg)

    result = build_failure_report(report)

    assert len(result["stages"]) == 1
    stage_entry = result["stages"][0]
    assert stage_entry["case_id"] == "case_a"
    assert stage_entry["stage"] == "decompose"
    assert stage_entry["tier"] == "stochastic"
    assert stage_entry["runs"] == 3
    assert stage_entry["errored_runs"] == 0
    assert stage_entry["error_samples"] == []
    check = stage_entry["failing_checks"]["variable_recall"]
    assert check["pass_rate"] == round(2 / 3, 4)
    assert check["failing_details"] == ["missing wind_speed"]


def test_build_failure_report_omits_stages_with_no_failures() -> None:
    report = AggregateReport()
    agg = StageAggregate(case_id="case_a", stage=Stage.PLAN, tier=Tier.DETERMINISTIC, runs=1)
    agg.observe("plan_forecast_count==1", True, "ok")
    report.add(agg)

    result = build_failure_report(report)

    assert result["stages"] == []


def test_build_failure_report_includes_errored_stage_with_no_checks() -> None:
    report = AggregateReport()
    agg = StageAggregate(
        case_id="case_a", stage=Stage.SYNTHESIZE, tier=Tier.STOCHASTIC, runs=1, errored_runs=1
    )
    agg.error_samples.append("boom")
    report.add(agg)

    result = build_failure_report(report)

    assert len(result["stages"]) == 1
    stage_entry = result["stages"][0]
    assert stage_entry["error_samples"] == ["boom"]
    assert stage_entry["failing_checks"] == {}


def test_build_failure_report_skips_stages_that_did_not_run() -> None:
    report = AggregateReport()
    report.add(StageAggregate(case_id="case_a", stage=Stage.SYNTHESIZE, tier=Tier.STOCHASTIC, runs=0))

    result = build_failure_report(report)

    assert result["stages"] == []


def test_build_failure_report_is_empty_for_a_report_with_no_stages() -> None:
    report = AggregateReport()

    result = build_failure_report(report)

    assert result == {"stages": [], "caching": None}


def test_save_failure_report_writes_valid_json_that_round_trips(tmp_path) -> None:
    report = AggregateReport()
    agg = StageAggregate(case_id="case_a", stage=Stage.DECOMPOSE, tier=Tier.STOCHASTIC, runs=2)
    agg.observe("variable_recall", False, "missing wind_speed")
    agg.observe("variable_recall", False, "missing wind_speed")
    report.add(agg)
    path = tmp_path / "failures.json"

    save_failure_report(report, str(path))

    with open(path) as f:
        loaded = json.load(f)
    assert loaded == build_failure_report(report)


def test_build_failure_report_includes_cache_stats_by_case_stage() -> None:
    report = AggregateReport()
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, cache_read_tokens=100),
        Usage(input_tokens=300, output_tokens=50, cache_read_tokens=0),
    ]

    result = build_failure_report(report)

    stats = result["caching"]["by_case_stage"]["case_a::decompose"]
    assert stats["calls"] == 2
    assert stats["mean_prompt_tokens"] == round(((200 + 100) + 300) / 2, 1)
    assert stats["cache_read_tokens_total"] == 100
    assert stats["cache_write_tokens_total"] == 0
    total = Usage(input_tokens=200, output_tokens=50, cache_read_tokens=100) + Usage(
        input_tokens=300, output_tokens=50, cache_read_tokens=0
    )
    assert stats["cache_hit_rate"] == round(total.cache_hit_rate, 4)


def test_build_failure_report_caching_is_none_without_usages() -> None:
    report = AggregateReport()
    agg = StageAggregate(case_id="case_a", stage=Stage.PLAN, tier=Tier.DETERMINISTIC, runs=1)
    agg.observe("plan_forecast_count==1", True, "ok")
    report.add(agg)

    result = build_failure_report(report)

    assert result["caching"] is None


def test_build_failure_report_caching_overall_folds_across_stages() -> None:
    report = AggregateReport()
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, cache_read_tokens=100)
    ]
    report.usages["case_a::synthesize"] = [
        Usage(input_tokens=800, output_tokens=150, cache_read_tokens=50)
    ]

    result = build_failure_report(report)

    overall = result["caching"]["overall"]
    assert overall["calls"] == 2
    assert overall["cache_read_tokens_total"] == 150
