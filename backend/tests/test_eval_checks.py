"""Unit tests for eval/harness/checks.py's decompose-scoring checks
(Task E1). Run offline against synthetic spec-shaped objects -- these
checks only ever read spec.location_names (and, for variables checks,
spec.variables), so a lightweight stand-in is enough; no real
DataNeedsSpec construction needed.
"""

from types import SimpleNamespace

from eval.harness import checks as C


def _spec(location_names: list[str]) -> SimpleNamespace:
    return SimpleNamespace(location_names=location_names)


def _spec_vars(variables: set[str]) -> SimpleNamespace:
    return SimpleNamespace(variables=variables)


def test_exact_match_passes() -> None:
    check = C.spec_locations_exact(["Paris"])
    passed, detail = check.predicate(_spec(["Paris"]))
    assert passed, detail


def test_case_insensitive_match_passes_by_default() -> None:
    check = C.spec_locations_exact(["Paris"])
    passed, detail = check.predicate(_spec(["paris"]))
    assert passed, detail


def test_case_sensitive_mode_fails_on_case_mismatch() -> None:
    check = C.spec_locations_exact(["Paris"], case_insensitive=False)
    passed, detail = check.predicate(_spec(["paris"]))
    assert not passed, detail


def test_case_sensitive_mode_passes_on_exact_case() -> None:
    check = C.spec_locations_exact(["Paris"], case_insensitive=False)
    passed, detail = check.predicate(_spec(["Paris"]))
    assert passed, detail


def test_wrong_city_fails() -> None:
    check = C.spec_locations_exact(["Paris"])
    passed, detail = check.predicate(_spec(["London"]))
    assert not passed, detail


def test_extra_city_fails() -> None:
    check = C.spec_locations_exact(["Paris"])
    passed, detail = check.predicate(_spec(["Paris", "London"]))
    assert not passed, detail


def test_missing_city_fails() -> None:
    check = C.spec_locations_exact(["Paris"])
    passed, detail = check.predicate(_spec([]))
    assert not passed, detail


def test_multi_location_unordered_match_passes() -> None:
    check = C.spec_locations_exact(["Tokyo", "Paris"])
    passed, detail = check.predicate(_spec(["Paris", "Tokyo"]))
    assert passed, detail


def test_duplicate_extracted_name_still_flags_the_missing_one() -> None:
    check = C.spec_locations_exact(["Tokyo", "Paris"])
    passed, detail = check.predicate(_spec(["Tokyo", "Tokyo"]))
    assert not passed, detail


def test_detail_reports_symmetric_difference() -> None:
    check = C.spec_locations_exact(["Paris", "Tokyo"])
    passed, detail = check.predicate(_spec(["Paris", "London"]))
    assert not passed
    assert "london" in detail.lower()
    assert "tokyo" in detail.lower()


# --- spec_variables_prf (Task E1.2) ---

_PRECIP_AND_CONDITION = {"PRECIP_PROBABILITY", "CONDITION"}


def test_exact_set_match_passes() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY", "CONDITION"}))
    assert passed, detail


def test_missing_variable_fails_recall_under_default_threshold() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY"}))
    assert not passed, detail


def test_extra_variable_fails_precision_under_default_threshold() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(
        _spec_vars({"PRECIP_PROBABILITY", "CONDITION", "WIND_SPEED"})
    )
    assert not passed, detail


def test_relaxed_min_precision_tolerates_extra_variable() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION, min_precision=0.6)
    passed, detail = check.predicate(
        _spec_vars({"PRECIP_PROBABILITY", "CONDITION", "WIND_SPEED"})
    )
    assert passed, detail


def test_relaxed_min_recall_tolerates_missing_variable() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION, min_recall=0.4)
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY"}))
    assert passed, detail


def test_completely_wrong_variables_fails_both_precision_and_recall() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(_spec_vars({"TEMPERATURE", "WIND_SPEED"}))
    assert not passed, detail


def test_detail_reports_precision_recall_and_offending_sets() -> None:
    check = C.spec_variables_prf(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY", "WIND_SPEED"}))
    assert not passed
    assert "precision" in detail.lower()
    assert "recall" in detail.lower()
    assert "wind_speed" in detail.lower()
    assert "condition" in detail.lower()


# --- spec_variables_exact (Task E1.3) ---


def test_spec_variables_exact_passes_for_exact_match() -> None:
    check = C.spec_variables_exact(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY", "CONDITION"}))
    assert passed, detail


def test_spec_variables_exact_fails_for_extra_variable() -> None:
    check = C.spec_variables_exact(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(
        _spec_vars({"PRECIP_PROBABILITY", "CONDITION", "WIND_SPEED"})
    )
    assert not passed, detail


def test_spec_variables_exact_fails_for_missing_variable() -> None:
    check = C.spec_variables_exact(_PRECIP_AND_CONDITION)
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY"}))
    assert not passed, detail
