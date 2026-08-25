from copy import deepcopy
import types
import unittest

from modules import ai_client
from modules.patient_dialogue import (
    assess_proposed_action,
    generate_interaction_evaluation,
    generate_patient_reply,
)
from modules.simulation_engine import (
    add_learner_dialogue,
    append_patient_response,
    case_by_id,
    load_cases,
    new_session,
    record_learner_dialogue,
    remove_latest_patient_response,
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
            "prompt",
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": {
                    "type": "object",
                    "properties": {"rating": {"type": "string"}},
                    "required": ["rating"],
                    "additionalProperties": False,
                },
            },
        )

        self.assertEqual(response.text, "A natural reply.")
        self.assertEqual(captured["model"], ai_client.OPENAI_DIALOGUE_MODEL)
        self.assertFalse(captured["store"])
        self.assertEqual(captured["max_output_tokens"], 350)
        self.assertEqual(captured["text"]["format"]["type"], "json_schema")
        self.assertTrue(captured["text"]["format"]["strict"])

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

    def test_interaction_evaluation_considers_action_and_words_together(self):
        captured = {}

        class FakeModel:
            def generate_content(self, prompt, generation_config=None):
                captured["prompt"] = prompt
                captured["config"] = generation_config
                return types.SimpleNamespace(
                    text=(
                        '{"rating":"appropriate","feedback":"The identity check is '
                        'appropriate and the explanation is respectful.","patient_reply":'
                        '"Yes, you can check my wristband."}'
                    )
                )

        before = deepcopy(self.session["state"])
        evaluation = generate_interaction_evaluation(
            case=self.case,
            session=self.session,
            state_before=before,
            action_text="I will check her identity using two identifiers.",
            dialogue_text="Hello Mrs Shaw, may I check your wristband and details?",
            action_status="applied",
            canonical_reply="The patient confirms her identity.",
            matched_action_label="Use two identifiers against the simulated record",
            model=FakeModel(),
        )

        self.assertTrue(evaluation.generated)
        self.assertEqual(evaluation.rating, "appropriate")
        self.assertIn("I will check her identity", captured["prompt"])
        self.assertIn("may I check your wristband", captured["prompt"])
        self.assertEqual(captured["config"]["response_mime_type"], "application/json")
        self.assertEqual(captured["config"]["response_schema"]["type"], "object")
        self.assertNotIn("facilitator_only", captured["prompt"])
        self.assertNotIn("expected_safety_points", captured["prompt"])

    def test_ai_assesses_unscripted_action_on_one_to_five_scale(self):
        captured = {}

        class FakeModel:
            def generate_content(self, prompt, generation_config=None):
                captured["prompt"] = prompt
                captured["config"] = generation_config
                return types.SimpleNamespace(
                    text=(
                        '{"matched_action_id":"check_identity","suitability_score":5,'
                        '"confidence":0.91,"rationale":"This is timely and supports safe '
                        'identification before further care."}'
                    )
                )

        assessment = assess_proposed_action(
            self.case,
            self.session,
            "Before anything else, I compare the wrist band with the record.",
            "Could I confirm your details first?",
            model=FakeModel(),
        )

        self.assertTrue(assessment.generated)
        self.assertEqual(assessment.matched_action_id, "check_identity")
        self.assertEqual(assessment.suitability_score, 5)
        self.assertEqual(assessment.suitability_band, "strongly_appropriate")
        self.assertAlmostEqual(assessment.confidence, 0.91)
        schema = captured["config"]["response_schema"]
        self.assertEqual(schema["properties"]["suitability_score"]["minimum"], 1)
        self.assertIn("check_identity", schema["properties"]["matched_action_id"]["enum"])
        self.assertIn("Consent and dignity", captured["prompt"])
        self.assertNotIn('"effects"', captured["prompt"])

    def test_reasonable_unbounded_action_can_be_scored_without_state_mapping(self):
        class FakeModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"matched_action_id":"none","suitability_score":4,'
                        '"confidence":0.88,"rationale":"This supports comfort without '
                        'claiming a clinical effect."}'
                    )
                )

        assessment = assess_proposed_action(
            self.case,
            self.session,
            "I adjust the pillows for comfort.",
            model=FakeModel(),
        )
        self.assertEqual(assessment.suitability_score, 4)
        self.assertIsNone(assessment.matched_action_id)
        self.assertTrue(assessment.generated)

    def test_blocked_action_rating_cannot_be_overridden_by_model(self):
        class OverlyPositiveModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"rating":"appropriate","feedback":"This seems fine.",'
                        '"patient_reply":"Please explain what you are doing."}'
                    )
                )

        evaluation = generate_interaction_evaluation(
            case=self.case,
            session=self.session,
            state_before=deepcopy(self.session["state"]),
            action_text="I will administer the charted option now.",
            dialogue_text="This will help.",
            action_status="blocked",
            canonical_reply="The safety checks are incomplete.",
            model=OverlyPositiveModel(),
        )
        self.assertEqual(evaluation.rating, "concerning")

    def test_combined_transcript_helpers_do_not_change_clinical_facts(self):
        original = deepcopy(self.session["state"])
        removed = remove_latest_patient_response(self.session)
        self.assertTrue(removed)
        record_learner_dialogue(
            self.case, self.session, "May I check your details?", minutes=0
        )
        append_patient_response(self.case, self.session, "Yes, that's fine.")
        self.assertEqual(self.session["state"], original)
        self.assertEqual(self.session["transcript"][-2]["role"], "learner_dialogue")
        self.assertEqual(self.session["transcript"][-1]["role"], "patient")


if __name__ == "__main__":
    unittest.main()
