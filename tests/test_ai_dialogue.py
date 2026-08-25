from copy import deepcopy
import types
import unittest

from modules import ai_client
from modules.patient_dialogue import generate_patient_reply
from modules.simulation_engine import (
    add_learner_dialogue,
    case_by_id,
    load_cases,
    new_session,
    replace_latest_patient_response,
)


class AiClientTests(unittest.TestCase):
    def tearDown(self):
        ai_client._provider = ai_client.GEMINI_PROVIDER
        ai_client._gemini_client = None
        ai_client._openai_client = None

    def test_openai_adapter_uses_non_stored_short_response(self):
        captured = {}

        class FakeResponses:
            def create(self, **kwargs):
                captured.update(kwargs)
                return types.SimpleNamespace(output_text="A natural reply.")

        ai_client._provider = ai_client.OPENAI_PROVIDER
        ai_client._openai_client = types.SimpleNamespace(responses=FakeResponses())
        response = ai_client.GenerativeModel(ai_client.DIALOGUE_MODEL).generate_content(
            "prompt"
        )

        self.assertEqual(response.text, "A natural reply.")
        self.assertEqual(captured["model"], ai_client.OPENAI_DIALOGUE_MODEL)
        self.assertFalse(captured["store"])
        self.assertEqual(captured["max_output_tokens"], 180)

    def test_gemini_adapter_preserves_generate_content_interface(self):
        captured = {}

        class FakeModels:
            def generate_content(self, **kwargs):
                captured.update(kwargs)
                return types.SimpleNamespace(text="A Gemini reply.")

        ai_client._provider = ai_client.GEMINI_PROVIDER
        ai_client._gemini_client = types.SimpleNamespace(models=FakeModels())
        response = ai_client.GenerativeModel(ai_client.DIALOGUE_MODEL).generate_content(
            "prompt"
        )

        self.assertEqual(response.text, "A Gemini reply.")
        self.assertEqual(captured["model"], ai_client.GEMINI_DIALOGUE_MODEL)


class PatientDialogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = case_by_id(load_cases(), "PAT-001")

    def setUp(self):
        self.session = new_session(self.case, "Test learner")

    def test_generated_reply_uses_safe_context_only(self):
        captured = {}

        class FakeModel:
            def generate_content(self, prompt):
                captured["prompt"] = prompt
                return types.SimpleNamespace(text="I would like you to explain that first.")

        reply = generate_patient_reply(
            self.case, self.session, "Would you like some pain relief?", model=FakeModel()
        )

        self.assertTrue(reply.generated)
        self.assertEqual(reply.text, "I would like you to explain that first.")
        self.assertNotIn("facilitator_only", captured["prompt"])
        self.assertNotIn("baseline_observations", captured["prompt"])
        self.assertNotIn("prescribed_items", captured["prompt"])

    def test_api_failure_uses_authored_fallback(self):
        class FailingModel:
            def generate_content(self, _prompt):
                raise RuntimeError("provider unavailable")

        reply = generate_patient_reply(
            self.case, self.session, "Hello", model=FailingModel()
        )
        self.assertFalse(reply.generated)
        self.assertTrue(reply.text)

    def test_generated_dose_is_rejected(self):
        class UnsafeModel:
            def generate_content(self, _prompt):
                return types.SimpleNamespace(text="You should give me 25 mg now.")

        reply = generate_patient_reply(
            self.case,
            self.session,
            "What do you need?",
            canonical_reply="Please explain the next step.",
            model=UnsafeModel(),
        )
        self.assertFalse(reply.generated)
        self.assertEqual(reply.text, "Please explain the next step.")

    def test_custom_dialogue_reply_does_not_change_state(self):
        original = deepcopy(self.session["state"])
        result = add_learner_dialogue(
            self.case,
            self.session,
            "How are you feeling?",
            reply_text="I am still uncomfortable when I move.",
        )
        self.assertTrue(result.applied)
        self.assertEqual(self.session["state"]["pain_score"], original["pain_score"])
        self.assertEqual(
            self.session["transcript"][-1]["text"],
            "I am still uncomfortable when I move.",
        )

    def test_latest_patient_wording_can_be_replaced_without_state_change(self):
        original = deepcopy(self.session["state"])
        changed = replace_latest_patient_response(self.session, "A revised natural reply.")
        self.assertTrue(changed)
        self.assertEqual(self.session["transcript"][-1]["text"], "A revised natural reply.")
        self.assertEqual(self.session["state"], original)


if __name__ == "__main__":
    unittest.main()
