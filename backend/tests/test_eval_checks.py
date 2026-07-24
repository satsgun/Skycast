"""Unit tests for eval/harness/checks.py's decompose-scoring checks
(Task E1) and synthesize-grounding checks (Task E4.2). Decompose checks
run offline against synthetic spec-shaped objects -- a lightweight
stand-in is enough since they only ever read spec.location_names/
.variables. Grounding checks need a real Forecast (derive_facts reads
real fields), so those use the domain types directly, same pattern as
test_eval_grounding.py.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

from skycast.domain.conditions import ConditionCode
from skycast.domain.forecast import Forecast, HourlyReading, Units
from skycast.domain.location import Location

from eval.cases.dataset import DATASET
from eval.harness import checks as C

_NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


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


# --- spec_has_variable (previously untested, now load-bearing for
# no_location_default below) ---


def test_spec_has_variable_passes_when_present() -> None:
    check = C.spec_has_variable("PRECIP_PROBABILITY")
    passed, detail = check.predicate(_spec_vars({"PRECIP_PROBABILITY", "CONDITION"}))
    assert passed, detail


def test_spec_has_variable_fails_when_absent() -> None:
    check = C.spec_has_variable("PRECIP_PROBABILITY")
    passed, detail = check.predicate(_spec_vars({"CONDITION"}))
    assert not passed, detail


# --- no_location_default's decompose checks (dataset.py) --
#
# Regression coverage for the composed "PRECIP_PROBABILITY required,
# CONDITION tolerated" rule: the decompose prompt's own guidance says a
# precip question "usually" also wants CONDITION (the same guidance that
# makes umbrella_decision expect it outright), so an exact-match check
# here was penalizing the model for correctly following its instructions.
# Imports the real DATASET so this guards dataset.py's actual wiring, not
# a parallel copy of the same expected-set literal.


def _default_location_spec(variables: set[str]) -> SimpleNamespace:
    return SimpleNamespace(location_names=[], use_default_location=True, variables=variables)


def _no_location_default_case():
    return next(c for c in DATASET if c.id == "no_location_default")


def _all_checks_pass(case, spec) -> bool:
    return all(check.predicate(spec)[0] for check in case.checks_decompose)


def test_no_location_default_passes_with_just_precip_probability() -> None:
    case = _no_location_default_case()
    assert _all_checks_pass(case, _default_location_spec({"PRECIP_PROBABILITY"}))


def test_no_location_default_tolerates_condition_as_well() -> None:
    case = _no_location_default_case()
    assert _all_checks_pass(
        case, _default_location_spec({"PRECIP_PROBABILITY", "CONDITION"})
    )


def test_no_location_default_rejects_other_extra_variables() -> None:
    case = _no_location_default_case()
    assert not _all_checks_pass(
        case, _default_location_spec({"PRECIP_PROBABILITY", "WIND_SPEED"})
    )


def test_no_location_default_still_requires_precip_probability() -> None:
    case = _no_location_default_case()
    assert not _all_checks_pass(case, _default_location_spec({"CONDITION"}))


# --- synthesize grounding checks (Task E4.2) ---


def _forecast(
    *,
    precip_probability: float | None = 10.0,
    temperature: float = 20.0,
    condition_code: ConditionCode = ConditionCode.CLEAR,
) -> Forecast:
    return Forecast(
        location=Location(id="test:x", name="X", latitude=0.0, longitude=0.0),
        units=Units(),
        current=HourlyReading(
            timestamp=_NOW,
            temperature=temperature,
            precip_probability=precip_probability,
            condition_code=condition_code,
        ),
    )


def _answer(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text)


def test_answer_grounded_precip_passes_for_affirmative_umbrella_over_rainy_fixture() -> None:
    check = C.answer_grounded_precip(_forecast(precip_probability=80.0))
    passed, detail = check.predicate(_answer("Yes, bring an umbrella this afternoon."))
    assert passed, detail


def test_answer_grounded_precip_fails_for_dry_and_sunny_over_rainy_fixture() -> None:
    check = C.answer_grounded_precip(_forecast(precip_probability=80.0))
    passed, detail = check.predicate(_answer("It'll be dry and sunny today."))
    assert not passed, detail


def test_answer_grounded_precip_passes_when_answer_never_mentions_rain() -> None:
    check = C.answer_grounded_precip(_forecast(precip_probability=80.0))
    passed, detail = check.predicate(_answer("It'll be a pleasant afternoon."))
    assert passed, detail


def test_answer_grounded_precip_passes_no_rain_expected_over_low_precip_fixture() -> None:
    check = C.answer_grounded_precip(_forecast(precip_probability=10.0))
    passed, detail = check.predicate(_answer("No rain expected today."))
    assert passed, detail


def test_answer_grounded_precip_fails_no_rain_expected_over_high_precip_fixture() -> None:
    check = C.answer_grounded_precip(_forecast(precip_probability=80.0))
    passed, detail = check.predicate(_answer("No rain expected today."))
    assert not passed, detail


def test_answer_grounded_precip_always_passes_when_fixture_has_no_precip_data() -> None:
    check = C.answer_grounded_precip(_forecast(precip_probability=None))
    passed, detail = check.predicate(_answer("Bring an umbrella just in case."))
    assert passed, detail


def test_answer_grounded_temperature_fails_for_warm_over_cold_fixture() -> None:
    check = C.answer_grounded_temperature(_forecast(temperature=5.0))
    passed, detail = check.predicate(_answer("It'll be a warm day."))
    assert not passed, detail


def test_answer_grounded_temperature_passes_for_chilly_over_cold_fixture() -> None:
    check = C.answer_grounded_temperature(_forecast(temperature=5.0))
    passed, detail = check.predicate(_answer("It'll be chilly today."))
    assert passed, detail


def test_answer_grounded_temperature_passes_when_answer_has_no_temperature_word() -> None:
    check = C.answer_grounded_temperature(_forecast(temperature=5.0))
    passed, detail = check.predicate(_answer("Bring an umbrella."))
    assert passed, detail


def test_answer_grounded_condition_fails_for_clear_skies_over_rain_fixture() -> None:
    check = C.answer_grounded_condition(_forecast(condition_code=ConditionCode.RAIN))
    passed, detail = check.predicate(_answer("Expect clear skies today."))
    assert not passed, detail


def test_answer_grounded_condition_passes_when_matching_rain_fixture() -> None:
    check = C.answer_grounded_condition(_forecast(condition_code=ConditionCode.RAIN))
    passed, detail = check.predicate(_answer("It'll be rainy today."))
    assert passed, detail


def test_answer_grounded_condition_passes_when_answer_is_silent() -> None:
    check = C.answer_grounded_condition(_forecast(condition_code=ConditionCode.RAIN))
    passed, detail = check.predicate(_answer("It'll be a good day for a walk."))
    assert passed, detail
