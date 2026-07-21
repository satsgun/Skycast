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
