"""Coverage for Task 23.5: print_cost surfaces the input/output/cache-
read/cache-write breakdown per stage plus an aggregate cache hit-rate,
instead of collapsing everything into a single mean-tokens number.
Also covers Task 23.6: an aggregate estimated-dollar-cost line, computed
via eval.harness.pricing.compute_cost -- the shared pricing path a
cache-on and a cache-off eval run both use, so the two runs' printed
costs are directly comparable.
"""

from __future__ import annotations

from eval.harness.aggregate import AggregateReport
from eval.harness.pricing import compute_cost
from eval.harness.report import print_cost
from skycast.llm.usage import Usage

_KNOWN_MODEL = "claude-haiku-4-5-20251001"


def test_print_cost_reports_per_stage_token_breakdown(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [100.0, 120.0]
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=100, output_tokens=20, cache_read_tokens=380, cache_write_tokens=20),
        Usage(input_tokens=100, output_tokens=20, cache_read_tokens=400, cache_write_tokens=0),
    ]

    print_cost(report)

    out = capsys.readouterr().out
    assert "decompose" in out
    assert "100 input" in out
    assert "20 output" in out
    assert "390 cache-read" in out
    assert "10 cache-write" in out


def test_print_cost_reports_aggregate_cache_hit_rate(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [100.0]
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=100, output_tokens=20, cache_read_tokens=800, cache_write_tokens=100)
    ]

    print_cost(report)

    out = capsys.readouterr().out
    total = Usage(input_tokens=100, output_tokens=20, cache_read_tokens=800, cache_write_tokens=100)
    assert f"cache hit-rate (aggregate across this run): {total.cache_hit_rate:.2f}" in out


def test_print_cost_falls_back_to_n_a_when_stage_has_no_usage_samples(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::plan"] = [5.0]
    # no report.usages entry for this stage -- e.g. a deterministic stage
    # or a stub client without last_usage.

    print_cost(report)

    out = capsys.readouterr().out
    assert "tokens n/a (not exposed by seam)" in out


def test_print_cost_hit_rate_is_zero_with_no_cache_activity_and_does_not_divide_by_zero(
    capsys,
) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::synthesize"] = [50.0]
    report.usages["case_a::synthesize"] = [Usage(input_tokens=50, output_tokens=10)]

    print_cost(report)

    out = capsys.readouterr().out
    assert "cache hit-rate (aggregate across this run): 0.00" in out


def test_print_cost_reports_aggregate_estimated_cost_for_a_known_model(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [100.0]
    usage = Usage(
        input_tokens=100,
        output_tokens=20,
        cache_read_tokens=800,
        cache_write_tokens=100,
        model=_KNOWN_MODEL,
    )
    report.usages["case_a::decompose"] = [usage]

    print_cost(report)

    out = capsys.readouterr().out
    expected = compute_cost(usage)
    assert f"estimated cost (aggregate across this run): ${expected:.4f}" in out


def test_print_cost_falls_back_to_cost_n_a_for_an_unrecognized_model(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [100.0]
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=100, output_tokens=20, model="some-future-model-nobody-priced-yet")
    ]

    print_cost(report)

    out = capsys.readouterr().out
    assert "cost n/a (no pricing data for model 'some-future-model-nobody-priced-yet')" in out
