from copy import deepcopy
import json
import types
import unittest

from modules.clinical_observations import (
    CHECK_ORDER,
    format_observation_results,
    generate_observations,
    requested_checks,
    validate_generated_observations,
)
from modules.simulation_engine import (
    case_by_id,
    clinical_check_block,
    load_cases,
    new_session,
    record_clinical_check,
    student_export,
)


class _ObservationModel:
    def __init__(self, values):
        self.values = values
        self.calls = 0

    def generate_content(self, _prompt, generation_config=None):
        self.calls += 1
        return types.SimpleNamespace(text=json.dumps(self.values))


class ClinicalObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()
        cls.pain_case = case_by_id(cls.cases, "PAT-001")
        cls.deterioration_case = case_by_id(cls.cases, "PAT-002")
        cls.conversation_case = case_by_id(cls.cases, "PAT-003")

    def test_common_observation_requests_are_recognised(self):
        self.assertEqual(requested_checks("I will check her BP."), ("blood_pressure",))
        self.assertEqual(
            requested_checks("I will record temperature and oxygen sats."),
            ("oxygen_saturation", "temperature"),
        )
        self.assertEqual(requested_checks("I will take a full set of observations."), CHECK_ORDER)

    def test_ai_values_are_bounded_to_authored_patient_baseline_and_cached(self):
        session = new_session(self.pain_case)
        model = _ObservationModel(
            {
                "respiratory_rate_per_min": 17,
                "oxygen_saturation_percent": 96,
                "oxygen_delivery": "room air",
                "heart_rate_per_min": 91,
                "systolic_blood_pressure_mmHg": 128,
                "diastolic_blood_pressure_mmHg": 76,
                "temperature_celsius": 36.9,
                "alertness": "alert",
            }
        )

        first = generate_observations(self.pain_case, session, model=model)
        second = generate_observations(self.pain_case, session, model=model)

        self.assertTrue(first.generated)
        self.assertEqual(first.values["systolic_blood_pressure_mmHg"], 128)
        self.assertEqual(second.values, first.values)
        self.assertEqual(model.calls, 1)

    def test_out_of_range_ai_values_fall_back_to_authored_baseline(self):
        session = new_session(self.pain_case)
        unsafe = _ObservationModel(
            {
                "respiratory_rate_per_min": 40,
                "oxygen_saturation_percent": 70,
                "oxygen_delivery": "room air",
                "heart_rate_per_min": 180,
                "systolic_blood_pressure_mmHg": 70,
                "diastolic_blood_pressure_mmHg": 60,
                "temperature_celsius": 41.0,
                "alertness": "unresponsive",
            }
        )

        result = generate_observations(self.pain_case, session, model=unsafe)

        self.assertFalse(result.generated)
        self.assertEqual(result.values["systolic_blood_pressure_mmHg"], 132)
        self.assertIn("safety check", result.notice)

    def test_deterioration_cannot_generate_improved_observations(self):
        baseline = {
            "respiratory_rate_per_min": 22,
            "oxygen_saturation_percent": 93,
            "oxygen_delivery": "room air",
            "heart_rate_per_min": 104,
            "systolic_blood_pressure_mmHg": 102,
            "diastolic_blood_pressure_mmHg": 64,
            "temperature_celsius": 38.1,
            "alertness": "new confusion",
        }
        improved = deepcopy(baseline)
        improved["respiratory_rate_per_min"] = 20
        improved["oxygen_saturation_percent"] = 95
        improved["systolic_blood_pressure_mmHg"] = 110

        with self.assertRaises(ValueError):
            validate_generated_observations(improved, baseline, deterioration_stage=1)

    def test_scenario_without_authored_baseline_never_invents_figures(self):
        result = generate_observations(
            self.conversation_case,
            new_session(self.conversation_case),
            model=_ObservationModel({}),
        )
        self.assertFalse(result.generated)
        self.assertEqual(result.values, {})
        self.assertIn("no educator-authored", result.notice)

    def test_results_include_only_requested_checks(self):
        values = {
            "respiratory_rate_per_min": 16,
            "oxygen_saturation_percent": 97,
            "oxygen_delivery": "room air",
            "heart_rate_per_min": 88,
            "systolic_blood_pressure_mmHg": 132,
            "diastolic_blood_pressure_mmHg": 78,
            "temperature_celsius": 36.8,
            "alertness": "alert",
        }
        text = format_observation_results(values, ("blood_pressure", "temperature"))
        self.assertIn("132/78 mmHg", text)
        self.assertIn("36.8 °C", text)
        self.assertNotIn("Oxygen", text)

    def test_check_result_is_logged_and_exported_without_changing_clinical_facts(self):
        session = new_session(self.pain_case)
        state_before = deepcopy(session["state"])
        result = record_clinical_check(
            self.pain_case,
            session,
            "I check the blood pressure.",
            "Blood pressure: 132/78 mmHg.",
            ("blood_pressure",),
            generated=True,
        )
        self.assertTrue(result.applied)
        expected = deepcopy(state_before)
        expected["elapsed_minutes"] += 2
        self.assertEqual(session["state"], expected)
        self.assertEqual(session["transcript"][-1]["source"], "bounded_ai")
        self.assertEqual(student_export(self.pain_case, session)["clinical_checks"][0]["checks"], ["blood_pressure"])

    def test_authored_observation_precondition_also_blocks_individual_checks(self):
        session = new_session(self.deterioration_case)
        self.assertIsNotNone(clinical_check_block(self.deterioration_case, session))
        session["state"]["identity_checked"] = True
        self.assertIsNone(clinical_check_block(self.deterioration_case, session))


if __name__ == "__main__":
    unittest.main()
