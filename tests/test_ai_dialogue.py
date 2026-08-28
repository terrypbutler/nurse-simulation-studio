from copy import deepcopy
import types
import unittest

from modules import ai_client
from modules.patient_dialogue import (
    ActionAssessment,
    action_requires_explicit_description,
    assess_interaction_actions,
    assess_proposed_action,
    authored_dialogue_fallback,
    authored_interaction_fallback,
    classify_interaction_intent,
    generate_interaction_evaluation,
    generate_patient_reply,
    recognised_action_can_apply,
)
from modules.simulation_engine import (
    add_learner_dialogue,
    append_patient_response,
    case_by_id,
    load_cases,
    new_session,
    record_unmapped_action,
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

    def test_openai_authoring_role_allows_full_non_stored_json_draft(self):
        captured = {}

        class FakeResponses:
            def create(self, **kwargs):
                captured.update(kwargs)
                return types.SimpleNamespace(output_text='{"scenario": {}}')

        ai_client._provider = ai_client.OPENAI_PROVIDER
        ai_client._openai_client = types.SimpleNamespace(responses=FakeResponses())
        response = ai_client.GenerativeModel(ai_client.AUTHORING_MODEL).generate_content(
            "authoring prompt",
            generation_config={"response_mime_type": "application/json"},
        )

        self.assertEqual(response.text, '{"scenario": {}}')
        self.assertFalse(captured["store"])
        self.assertEqual(captured["reasoning"]["effort"], "low")
        self.assertEqual(captured["max_output_tokens"], 7000)
        self.assertEqual(captured["text"]["format"]["type"], "json_object")


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
        self.assertIn("authored_dialogue_facts", captured["prompt"])
        self.assertIn("7 out of 10", captured["prompt"])

    def test_api_failure_uses_authored_fallback(self):
        class FailingModel:
            def generate_content(self, _prompt):
                raise RuntimeError("provider unavailable")

        reply = generate_patient_reply(
            self.case, self.session, "Hello", model=FailingModel()
        )
        self.assertFalse(reply.generated)
        self.assertTrue(reply.text)

    def test_introduction_fallback_corrects_preferred_address(self):
        reply, intent = authored_interaction_fallback(
            self.case,
            self.session,
            "Introduce myself",
            "Hello Miss Shaw, I am Terry. I'm a trainee nurse.",
        )
        self.assertEqual(intent, "address_correction")
        self.assertEqual(reply, "It's Mrs Shaw, please.")

    def test_medication_history_is_separate_from_record_check(self):
        intent = classify_interaction_intent(
            self.case,
            "Check medication",
            "I'm going to see what medication you are on.",
        )
        reply, fallback_intent = authored_interaction_fallback(
            self.case,
            self.session,
            "Check medication",
            "I'm going to see what medication you are on.",
        )
        self.assertEqual(intent, "medication_history")
        self.assertEqual(fallback_intent, intent)
        self.assertIn("usual medicines", reply)

    def test_supportive_fallback_turn_is_unscored_but_appropriate(self):
        class FailingModel:
            def generate_content(self, _prompt, generation_config=None):
                raise RuntimeError("provider unavailable")

        reply, intent = authored_interaction_fallback(
            self.case,
            self.session,
            "Introduce myself",
            "Hello Mrs Shaw, I am Terry, a trainee nurse.",
        )
        evaluation = generate_interaction_evaluation(
            case=self.case,
            session=self.session,
            state_before=deepcopy(self.session["state"]),
            action_text="Introduce myself",
            dialogue_text="Hello Mrs Shaw, I am Terry, a trainee nurse.",
            action_status="supportive_only",
            canonical_reply=reply,
            interaction_intent=intent,
            model=FailingModel(),
        )
        self.assertEqual(evaluation.rating, "appropriate")
        self.assertIn("supportive communication", evaluation.feedback)
        self.assertEqual(evaluation.patient_reply, reply)

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

    def test_exact_recent_patient_reply_is_rejected(self):
        opening = self.session["transcript"][0]["text"]

        class RepeatingModel:
            def generate_content(self, _prompt):
                return types.SimpleNamespace(text=opening)

        reply = generate_patient_reply(
            self.case,
            self.session,
            "Can you tell me again?",
            canonical_reply="Could you ask me a more specific question?",
            model=RepeatingModel(),
        )
        self.assertFalse(reply.generated)
        self.assertEqual(reply.text, "Could you ask me a more specific question?")

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
                        '"Yes, you can check my wristband.","nonverbal_cue":'
                        '"Mrs Shaw pauses before answering and keeps one hand protectively '
                        'over her operated side.","response_latency":"brief_pause"}'
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
        self.assertEqual(evaluation.response_latency, "brief_pause")
        self.assertIn("Mrs Shaw pauses", evaluation.nonverbal_cue)
        self.assertIn("I will check her identity", captured["prompt"])
        self.assertIn("may I check your wristband", captured["prompt"])
        self.assertEqual(captured["config"]["response_mime_type"], "application/json")
        self.assertEqual(captured["config"]["response_schema"]["type"], "object")
        required = captured["config"]["response_schema"]["required"]
        self.assertIn("disclosed_fact_ids", required)
        self.assertIn("conversation_move", required)
        self.assertIn(
            evaluation.nonverbal_cue,
            captured["config"]["response_schema"]["properties"]["nonverbal_cue"]["enum"],
        )
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
                        '"relevance_category":"direct",'
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
        self.assertEqual(assessment.relevance_category, "direct")
        self.assertAlmostEqual(assessment.confidence, 0.91)
        schema = captured["config"]["response_schema"]
        self.assertEqual(schema["properties"]["suitability_score"]["minimum"], 1)
        self.assertIn("check_identity", schema["properties"]["matched_action_id"]["enum"])
        self.assertIn("Consent and dignity", captured["prompt"])
        self.assertIn("case_specific_educator_rubric", captured["prompt"])
        self.assertNotIn('"effects"', captured["prompt"])

    def test_spoken_words_can_map_multiple_conversational_actions(self):
        captured = {}

        class FakeModel:
            def generate_content(self, prompt, generation_config=None):
                captured["prompt"] = prompt
                captured["schema"] = generation_config["response_schema"]
                return types.SimpleNamespace(
                    text=(
                        '{"matched_actions":['
                        '{"action_id":"check_identity","confidence":0.94,'
                        '"evidence_source":"spoken_words"},'
                        '{"action_id":"assess_pain","confidence":0.9,'
                        '"evidence_source":"spoken_words"}],'
                        '"suitability_score":5,"relevance_category":"direct",'
                        '"rationale":"The learner clearly checks identity and then explores pain."}'
                    )
                )

        assessment = assess_interaction_actions(
            self.case,
            self.session,
            dialogue_text=(
                "Could you confirm your name and date of birth? Then tell me where "
                "the pain is and what it feels like."
            ),
            model=FakeModel(),
        )

        self.assertEqual(
            assessment.matched_action_ids,
            ("check_identity", "assess_pain"),
        )
        self.assertEqual(
            assessment.evidence_sources,
            ("spoken_words", "spoken_words"),
        )
        self.assertIn("recent_learner_evidence", captured["prompt"])
        self.assertEqual(
            captured["schema"]["properties"]["matched_actions"]["maxItems"], 3
        )

    def test_turn_assessment_returns_quote_linked_rubric_evidence(self):
        words = "Could you tell me where the pain is and how it affects your movement?"

        class FakeModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"matched_actions":[{"action_id":"assess_pain",'
                        '"confidence":0.94,"evidence_source":"spoken_words"}],'
                        '"suitability_score":5,"relevance_category":"direct",'
                        '"rationale":"A focused person-centred assessment.",'
                        '"criterion_evidence":[{"criterion_id":"assessment",'
                        '"finding":"demonstrated","evidence_quote":"' + words + '",'
                        '"rationale":"The learner explores site and functional impact.",'
                        '"confidence":0.93}]}'
                    )
                )

        assessment = assess_interaction_actions(
            self.case,
            self.session,
            dialogue_text=words,
            model=FakeModel(),
        )
        self.assertEqual(len(assessment.rubric_findings), 1)
        finding = assessment.rubric_findings[0]
        self.assertEqual(finding.criterion_id, "assessment")
        self.assertEqual(finding.finding, "demonstrated")
        self.assertEqual(finding.evidence_quote, words)

    def test_untraceable_rubric_quote_is_ignored(self):
        class FakeModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"matched_actions":[],"suitability_score":3,'
                        '"relevance_category":"unclear","rationale":"Needs review.",'
                        '"criterion_evidence":[{"criterion_id":"assessment",'
                        '"finding":"demonstrated","evidence_quote":"I completed everything",'
                        '"rationale":"Unsupported quotation.","confidence":0.9}]}'
                    )
                )

        assessment = assess_interaction_actions(
            self.case,
            self.session,
            dialogue_text="How are you feeling?",
            model=FakeModel(),
        )
        self.assertEqual(assessment.rubric_findings, ())

    def test_safety_critical_action_is_rejected_from_spoken_words_alone(self):
        class FakeModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"matched_actions":[{"action_id":"administer_charted_option",'
                        '"confidence":0.99,"evidence_source":"proposed_action"}],'
                        '"suitability_score":5,"relevance_category":"direct",'
                        '"rationale":"The learner mentions giving pain relief."}'
                    )
                )

        assessment = assess_interaction_actions(
            self.case,
            self.session,
            dialogue_text="I can give you the pain relief now.",
            model=FakeModel(),
        )

        self.assertEqual(assessment.matched_action_ids, ())
        action = next(
            item
            for item in self.case["allowed_actions"]
            if item["action_id"] == "administer_charted_option"
        )
        self.assertTrue(action_requires_explicit_description(action))

    def test_safety_critical_action_can_map_from_explicit_action_description(self):
        class FakeModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"matched_actions":[{"action_id":"administer_charted_option",'
                        '"confidence":0.95,"evidence_source":"both"}],'
                        '"suitability_score":4,"relevance_category":"direct",'
                        '"rationale":"The proposed action explicitly describes administration."}'
                    )
                )

        assessment = assess_interaction_actions(
            self.case,
            self.session,
            action_text="I administer the verified charted option.",
            dialogue_text="I am going to give this now, with your agreement.",
            model=FakeModel(),
        )

        self.assertEqual(
            assessment.matched_action_ids,
            ("administer_charted_option",),
        )

    def test_recognised_action_can_apply_even_when_formative_score_is_low(self):
        assessment = ActionAssessment(
            "check_identity",
            2,
            "concerning",
            "direct",
            0.92,
            "The wording is impersonal, but an identity check is clearly performed.",
            True,
        )
        action = next(
            item
            for item in self.case["allowed_actions"]
            if item["action_id"] == "check_identity"
        )
        self.assertTrue(
            recognised_action_can_apply(
                assessment,
                action,
                0.92,
                "spoken_words",
                "",
            )
        )

    def test_counterproductive_action_can_progress_for_debrief(self):
        assessment = ActionAssessment(
            "check_identity",
            1,
            "clearly_concerning",
            "counterproductive",
            0.95,
            "The action conflicts with dignity and safety.",
            True,
        )
        action = next(
            item
            for item in self.case["allowed_actions"]
            if item["action_id"] == "check_identity"
        )
        self.assertTrue(
            recognised_action_can_apply(
                assessment,
                action,
                0.95,
                "both",
                "I check identity.",
            )
        )

    def test_action_only_turn_advances_authored_fallback_reply(self):
        first = authored_dialogue_fallback(self.case, self.session)
        record_unmapped_action(
            self.case,
            self.session,
            "I wait quietly for a moment.",
            supportive=True,
        )
        second = authored_dialogue_fallback(self.case, self.session)
        self.assertNotEqual(first, second)

    def test_reasonable_unbounded_action_can_be_scored_without_state_mapping(self):
        class FakeModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"matched_action_id":"none","suitability_score":4,'
                        '"relevance_category":"supportive",'
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
        self.assertEqual(assessment.relevance_category, "supportive")
        self.assertIsNone(assessment.matched_action_id)
        self.assertTrue(assessment.generated)

    def test_blocked_action_rating_cannot_be_overridden_by_model(self):
        class OverlyPositiveModel:
            def generate_content(self, _prompt, generation_config=None):
                return types.SimpleNamespace(
                    text=(
                        '{"rating":"appropriate","feedback":"This seems fine.",'
                        '"patient_reply":"Please explain what you are doing.",'
                        '"nonverbal_cue":"","response_latency":"immediate"}'
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
        append_patient_response(
            self.case,
            self.session,
            "Yes, that's fine.",
            nonverbal_cue=self.case["patient"]["nonverbal_palette"][0],
            response_latency="brief_pause",
            disclosed_fact_ids=("fact_1",),
            conversation_move="answer",
        )
        self.assertEqual(self.session["state"], original)
        self.assertEqual(self.session["transcript"][-3]["role"], "learner_dialogue")
        self.assertEqual(self.session["transcript"][-2]["role"], "nonverbal")
        self.assertEqual(self.session["transcript"][-1]["role"], "patient")
        self.assertIn(
            "fact_1",
            self.session["conversation_memory"]["disclosed_fact_ids"],
        )
        self.assertEqual(
            self.session["conversation_memory"]["recent_conversation_moves"][-1],
            "answer",
        )


if __name__ == "__main__":
    unittest.main()
