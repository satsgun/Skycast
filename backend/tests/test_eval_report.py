"""Coverage for Task 23.5: print_cost surfaces the input/output/cache-
read/cache-write breakdown per stage plus an aggregate cache hit-rate,
instead of collapsing everything into a single mean-tokens number.
Also covers Task 23.6: an aggregate estimated-dollar-cost line, computed
via eval.harness.cost.cost_of (Task 24.2) -- the shared pricing path a
cache-on and a cache-off eval run both use, so the two runs' printed
costs are directly comparable.

Task 24.4 adds: per-stage mean $ cost, a per-query section (decompose
vs. synthesize split, per-model $/query, an unpriced-models line), and
a within-run counterfactual "what if this hadn't been cached" figure.
The per-query numbers pair each case's decompose/synthesize Usage
samples by run-index (see report.py's _per_query_costs docstring) --
that pairing is a cost proxy, so these tests treat only the *mean*
over paired queries as meaningful, matching how print_cost itself
labels the output.
"""

from __future__ import annotations

from eval.harness.aggregate import AggregateReport
from eval.harness.cost import cost_of, query_cost
from eval.harness.report import print_cost
from skycast.llm.usage import Usage

_KNOWN_MODEL = "claude-haiku-4-5-20251001"
_OTHER_KNOWN_MODEL = "claude-sonnet-4-5"


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


def test_print_cost_reports_per_stage_mean_dollar_cost_for_a_known_model(capsys) -> None:
    usages = [
        Usage(input_tokens=100, output_tokens=20, model=_KNOWN_MODEL),
        Usage(input_tokens=200, output_tokens=40, model=_KNOWN_MODEL),
    ]
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [100.0, 100.0]
    report.usages["case_a::decompose"] = usages

    print_cost(report)

    out = capsys.readouterr().out
    mean_input_cost = sum(cost_of(u).input_cost for u in usages) / len(usages)
    mean_output_cost = sum(cost_of(u).output_cost for u in usages) / len(usages)
    assert f"${mean_input_cost:.4f} input" in out
    assert f"${mean_output_cost:.4f} output cost" in out


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
    expected = cost_of(usage).total_cost
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


# --- Task 24.4: per-query section ---


def test_print_cost_reports_mean_per_query_cost_with_decompose_synthesize_split(capsys) -> None:
    decompose_usages = [
        Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL),
        Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL),
    ]
    synthesize_usages = [
        Usage(input_tokens=800, output_tokens=150, model=_KNOWN_MODEL),
        Usage(input_tokens=800, output_tokens=150, model=_KNOWN_MODEL),
    ]
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [10.0, 10.0]
    report.timings_ms["case_a::synthesize"] = [10.0, 10.0]
    report.usages["case_a::decompose"] = decompose_usages
    report.usages["case_a::synthesize"] = synthesize_usages

    print_cost(report)

    out = capsys.readouterr().out
    queries = [query_cost(d, s) for d, s in zip(decompose_usages, synthesize_usages)]
    mean_total = sum(q.total_cost for q in queries) / len(queries)
    mean_decompose = sum(q.decompose.total_cost for q in queries) / len(queries)
    mean_synthesize = sum(q.synthesize.total_cost for q in queries) / len(queries)
    assert "mean per-query cost" in out
    assert "run-index paired" in out
    assert f"${mean_total:.4f}/query" in out
    assert f"${mean_decompose:.4f}/query" in out
    assert f"${mean_synthesize:.4f}/query" in out


def test_print_cost_per_query_handles_a_case_that_never_reaches_synthesize(capsys) -> None:
    """A case with no f"{case_id}::synthesize" key at all -- the eval
    harness's equivalent of the clarify path never synthesizing (Task
    24.3) -- must not break the per-query section, and since no case in
    this report ever reached synthesize, the synthesize split falls
    back to n/a rather than a bogus mean over zero samples.
    """
    decompose_usages = [Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)]
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [10.0]
    report.usages["case_a::decompose"] = decompose_usages

    print_cost(report)

    out = capsys.readouterr().out
    expected_total = cost_of(decompose_usages[0]).total_cost
    assert f"${expected_total:.4f}/query" in out
    assert "synthesize: n/a" in out


def test_print_cost_reports_per_model_mean_cost_per_query(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [10.0]
    report.timings_ms["case_b::decompose"] = [10.0]
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, model=_KNOWN_MODEL)
    ]
    report.usages["case_b::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, model=_OTHER_KNOWN_MODEL)
    ]

    print_cost(report)

    out = capsys.readouterr().out
    assert f"{_KNOWN_MODEL}: $" in out
    assert f"{_OTHER_KNOWN_MODEL}: $" in out


def test_print_cost_names_unpriced_models_in_the_per_query_section(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [10.0]
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=200, output_tokens=50, model="gpt-4o")
    ]

    print_cost(report)

    out = capsys.readouterr().out
    assert "unpriced" in out
    assert "gpt-4o" in out


# --- Task 24.4: within-run counterfactual ---


def test_print_cost_reports_counterfactual_uncached_cost_and_savings(capsys) -> None:
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
    real_cost = cost_of(usage).total_cost
    counterfactual_usage = Usage(
        input_tokens=usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens,
        output_tokens=usage.output_tokens,
        model=usage.model,
    )
    counterfactual_cost = cost_of(counterfactual_usage).total_cost
    assert f"counterfactual uncached cost (same tokens, no caching): ${counterfactual_cost:.4f}" in out
    assert f"saved by caching (within this run): ${counterfactual_cost - real_cost:.4f}" in out


def test_print_cost_omits_counterfactual_when_there_is_no_cache_activity(capsys) -> None:
    report = AggregateReport()
    report.timings_ms["case_a::decompose"] = [100.0]
    report.usages["case_a::decompose"] = [
        Usage(input_tokens=100, output_tokens=20, model=_KNOWN_MODEL)
    ]

    print_cost(report)

    out = capsys.readouterr().out
    assert "counterfactual" not in out
    assert "saved by caching" not in out
