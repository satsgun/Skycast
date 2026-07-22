"""Coverage for Task 24.5: build_cost_summary/save_cost_summary produce
a committable JSON snapshot of the same numbers print_cost already
prints (per-query mean cost with the decompose/synthesize split,
per-model mean cost, unpriced models, token totals, cache hit-rate) --
never a silently-fabricated 0 or crash when there's nothing to report.
"""

from __future__ import annotations

import json

from eval.harness.aggregate import AggregateReport
from eval.harness.cost import cost_of, query_cost
from eval.harness.cost_summary import build_cost_summary, save_cost_summary
from skycast.llm.usage import Usage

_KNOWN_MODEL = "claude-haiku-4-5-20251001"


def test_build_cost_summary_reports_all_fields_for_a_normal_run() -> None:
    decompose_usages = [
        Usage(input_tokens=200, output_tokens=50, cache_read_tokens=100, model=_KNOWN_MODEL),
        Usage(input_tokens=200, output_tokens=50, cache_read_tokens=100, model=_KNOWN_MODEL),
    ]
    synthesize_usages = [
        Usage(input_tokens=800, output_tokens=150, model=_KNOWN_MODEL),
        Usage(input_tokens=800, output_tokens=150, model=_KNOWN_MODEL),
    ]
    report = AggregateReport()
    report.usages["case_a::decompose"] = decompose_usages
    report.usages["case_a::synthesize"] = synthesize_usages

    summary = build_cost_summary(report)

    queries = [query_cost(d, s) for d, s in zip(decompose_usages, synthesize_usages)]
    expected_mean_total = sum(q.total_cost for q in queries) / len(queries)
    expected_mean_decompose = sum(q.decompose.total_cost for q in queries) / len(queries)
    expected_mean_synthesize = sum(q.synthesize.total_cost for q in queries) / len(queries)

    assert summary["mean_cost_per_query"] == round(expected_mean_total, 6)
    assert summary["stage_split"]["decompose"]["mean_cost_per_query"] == round(
        expected_mean_decompose, 6
    )
    assert summary["stage_split"]["decompose"]["n"] == 2
    assert summary["stage_split"]["synthesize"]["mean_cost_per_query"] == round(
        expected_mean_synthesize, 6
    )
    assert summary["stage_split"]["synthesize"]["n"] == 2
    assert summary["per_model_mean_query_cost"][_KNOWN_MODEL] == round(expected_mean_total, 6)
    assert summary["unpriced_models"] == []

    total_usage = decompose_usages[0] + decompose_usages[1] + synthesize_usages[0] + synthesize_usages[1]
    assert summary["token_totals"] == {
        "input_tokens": total_usage.input_tokens,
        "output_tokens": total_usage.output_tokens,
        "cache_read_tokens": total_usage.cache_read_tokens,
        "cache_write_tokens": total_usage.cache_write_tokens,
        "total_tokens": total_usage.total_tokens,
    }
    assert summary["cache_hit_rate"] == round(total_usage.cache_hit_rate, 4)


def test_build_cost_summary_handles_a_case_that_never_reaches_synthesize() -> None:
    report = AggregateReport()
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)
    ]

    summary = build_cost_summary(report)

    assert summary["stage_split"]["synthesize"] == {"mean_cost_per_query": None, "n": 0}
    assert summary["stage_split"]["decompose"]["n"] == 1


def test_build_cost_summary_names_unpriced_models() -> None:
    report = AggregateReport()
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, model="gpt-4o")
    ]

    summary = build_cost_summary(report)

    assert summary["unpriced_models"] == ["gpt-4o"]
    assert summary["mean_cost_per_query"] is None


def test_build_cost_summary_is_all_none_and_empty_for_an_empty_report() -> None:
    report = AggregateReport()

    summary = build_cost_summary(report)

    assert summary == {
        "mean_cost_per_query": None,
        "stage_split": {
            "decompose": {"mean_cost_per_query": None, "n": 0},
            "synthesize": {"mean_cost_per_query": None, "n": 0},
        },
        "per_model_mean_query_cost": {},
        "unpriced_models": [],
        "token_totals": None,
        "cache_hit_rate": None,
    }


def test_save_cost_summary_writes_valid_json_that_round_trips(tmp_path) -> None:
    report = AggregateReport()
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)
    ]
    path = tmp_path / "cost_summary.json"

    save_cost_summary(report, str(path))

    with open(path) as f:
        loaded = json.load(f)
    assert loaded == build_cost_summary(report)
