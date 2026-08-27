from copy import deepcopy
import json
from pathlib import Path
import unittest

from modules.scenario_authoring import generate_scenario_draft


ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModel:
    def __init__(self, payloads):
        self.payloads = iter(payloads)
        self.calls = []

    def generate_content(self, prompt, generation_config=None):
        self.calls.append((prompt, generation_config))
        return FakeResponse(next(self.payloads))


class ScenarioAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = json.loads(
            (ROOT / "sample_patients" / "patient_cases.json").read_text(encoding="utf-8")
        )
        cls.base = library["cases"][0]

    def test_plain_language_request_becomes_valid_hardened_draft(self):
        candidate = deepcopy(self.base)
        candidate["case_id"] = "PAT-999"
        candidate["title"] = "A newly described fictional encounter"
        candidate["synthetic_data_notice"] = "changed"
        candidate["publication_status"] = "approved"
        candidate["debrief"]["automatic_competence_decision"] = True
        model = FakeModel([json.dumps(candidate)])

        result = generate_scenario_draft(
            self.base,
            "Create a fictional discharge conversation where a learner uses teach-back and supports accessible communication.",
            "PAT-005",
            model=model,
        )

        self.assertIsNotNone(result.case)
        self.assertEqual(result.case["case_id"], "PAT-005")
        self.assertEqual(result.case["synthetic_data_notice"], "Entirely fictional training case")
        self.assertEqual(result.case["publication_status"], "development")
        self.assertFalse(result.case["debrief"]["automatic_competence_decision"])
        self.assertEqual(model.calls[0][1], {"response_mime_type": "application/json"})

    def test_invalid_first_response_is_repaired_once(self):
        repaired = deepcopy(self.base)
        repaired["title"] = "Repaired fictional scenario draft"
        model = FakeModel(["not json", json.dumps(repaired)])

        result = generate_scenario_draft(
            self.base,
            "Create a fictional scenario that practises a clear handover and respectful escalation.",
            "PAT-005",
            model=model,
        )

        self.assertIsNotNone(result.case)
        self.assertEqual(len(model.calls), 2)

    def test_very_short_request_is_rejected_without_ai_call(self):
        model = FakeModel([])
        result = generate_scenario_draft(self.base, "Make one", "PAT-005", model=model)
        self.assertIsNone(result.case)
        self.assertIn("more detail", result.error)
        self.assertEqual(model.calls, [])


if __name__ == "__main__":
    unittest.main()
