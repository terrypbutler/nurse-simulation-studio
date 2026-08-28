from copy import deepcopy
import unittest

from modules.simulation_engine import (
    add_learner_action,
    add_learner_dialogue,
    apply_action,
    case_by_id,
    end_session,
    load_cases,
    match_action_id,
    new_session,
    record_blocked_attempt,
    record_nursing_note,
    record_unmapped_action,
    start_session,
    student_export,
    session_reached_duration,
    session_repeated_blocked_action,
)


class SimulationEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()

    def setUp(self):
        self.case = case_by_id(self.cases, "PAT-001")
        self.original = deepcopy(self.case)
        self.session = new_session(self.case, "Test learner")

    def test_new_session_does_not_mutate_case(self):
        self.session["state"]["pain_score"] = 1
        self.assertEqual(self.case, self.original)
        self.assertEqual(self.case["initial_state"]["pain_score"], 7)

    def test_prebrief_blocks_actions_until_learner_starts(self):
        session = new_session(
            self.case,
            "Test learner",
            practice_mode="immersive",
            start_in_prebrief=True,
        )
        blocked = apply_action(self.case, session, "check_identity")
        self.assertFalse(blocked.applied)
        self.assertEqual(session["phase"], "prebrief")
        start_session(session)
        result = apply_action(self.case, session, "check_identity")
        self.assertTrue(result.applied)
        self.assertEqual(session["practice_mode"], "immersive")

    def test_case_specific_rubric_is_copied_into_session(self):
        self.session["educator_rubric"][0]["guidance"] = "Changed for this rehearsal"
        self.assertNotEqual(
            self.session["educator_rubric"][0]["guidance"],
            self.case["educator_rubric"][0]["guidance"],
        )

    def test_precondition_blocks_unsafe_action(self):
        result = apply_action(self.case, self.session, "administer_charted_option")
        self.assertFalse(result.applied)
        self.assertFalse(self.session["state"]["analgesia_administered"])
        self.assertEqual(self.session["state"]["elapsed_minutes"], 0)

    def test_blocked_attempt_advances_time_without_applying_effects(self):
        original = deepcopy(self.session["state"])
        blocked = apply_action(
            self.case, self.session, "administer_charted_option"
        )
        recorded = record_blocked_attempt(
            self.case,
            self.session,
            "administer_charted_option",
            "I administer the charted option.",
            blocked.message,
        )
        self.assertTrue(recorded.applied)
        self.assertEqual(self.session["state"]["elapsed_minutes"], 2)
        self.assertEqual(
            self.session["state"]["analgesia_administered"],
            original["analgesia_administered"],
        )
        self.assertEqual(self.session["action_log"][-1]["status"], "blocked")
        self.assertFalse(self.session["action_log"][-1]["applied"])

    def test_authored_duration_can_end_session_with_reason(self):
        self.session["state"]["elapsed_minutes"] = (
            self.case["estimated_duration_minutes"]
        )
        self.assertTrue(session_reached_duration(self.case, self.session))
        end_session(self.session, reason="planned_duration")
        exported = student_export(self.case, self.session)
        self.assertEqual(exported["status"], "ended")
        self.assertEqual(exported["end_reason"], "planned_duration")

    def test_repeated_blocked_action_can_end_stalled_session(self):
        for _ in range(3):
            blocked = apply_action(
                self.case, self.session, "administer_charted_option"
            )
            record_blocked_attempt(
                self.case,
                self.session,
                "administer_charted_option",
                "I administer the charted option.",
                blocked.message,
            )
        self.assertTrue(session_repeated_blocked_action(self.session))
        end_session(self.session, reason="repeated_blocked_action")
        self.assertEqual(self.session["end_reason"], "repeated_blocked_action")

    def test_safe_pain_path_and_deltas(self):
        apply_action(self.case, self.session, "check_identity")
        apply_action(self.case, self.session, "assess_pain")
        apply_action(self.case, self.session, "check_allergies_and_prescription")
        apply_action(self.case, self.session, "explain_analgesia")
        apply_action(self.case, self.session, "seek_consent")
        result = apply_action(self.case, self.session, "administer_charted_option")
        self.assertTrue(result.applied)
        self.assertTrue(self.session["state"]["analgesia_administered"])
        self.assertEqual(self.session["state"]["consent_state"], "accepted")
        self.assertGreater(self.session["state"]["trust"], 45)

    def test_time_event_fires_once(self):
        for _ in range(4):
            add_learner_dialogue(self.case, self.session, "Hello", minutes=2)
        self.assertIn("pain_unaddressed", self.session["resolved_events"])
        self.assertEqual(self.session["state"]["pain_score"], 8)
        cue_count = len(self.session["state"]["revealed_cues"])
        add_learner_dialogue(self.case, self.session, "Another question", minutes=2)
        self.assertEqual(len(self.session["state"]["revealed_cues"]), cue_count)

    def test_due_event_waits_for_its_authored_condition(self):
        case = case_by_id(self.cases, "PAT-004")
        session = new_session(case, "Test learner")
        for _ in range(3):
            add_learner_dialogue(case, session, "I am explaining what I am doing.", minutes=2)
        self.assertNotIn("withdraw_consent", session["resolved_events"])
        session["state"]["consent_state"] = "accepted"
        result = apply_action(case, session, "start_agreed_care")
        self.assertTrue(result.applied)
        self.assertIn("withdraw_consent", result.fired_events)
        self.assertEqual(session["state"]["consent_state"], "withdrawn")

    def test_nursing_note_advances_time_and_is_exported(self):
        result = record_nursing_note(
            self.case,
            self.session,
            "Pain assessed and concern about drowsiness acknowledged.",
        )
        self.assertTrue(result.applied)
        self.assertEqual(self.session["state"]["elapsed_minutes"], 1)
        exported = student_export(self.case, self.session)
        self.assertEqual(len(exported["nursing_notes"]), 1)

    def test_patient_experience_values_remain_bounded(self):
        for _ in range(20):
            apply_action(self.case, self.session, "assess_pain", minutes=0)
        self.assertEqual(self.session["state"]["trust"], 100)

    def test_free_text_action_matches_authored_action(self):
        result = add_learner_action(
            self.case, self.session, "I will confirm her identity using two identifiers."
        )
        self.assertTrue(result.applied)
        self.assertTrue(self.session["state"]["identity_checked"])
        self.assertEqual(
            self.session["transcript"][1]["text"],
            "I will confirm her identity using two identifiers.",
        )

    def test_action_match_is_case_specific(self):
        self.assertEqual(
            match_action_id(self.case, "I will assess her pain and ask for a pain score."),
            "assess_pain",
        )
        self.assertIsNone(match_action_id(self.case, "I will take a blood sample."))

    def test_identity_variants_match_without_scripted_phrases(self):
        self.assertEqual(
            match_action_id(
                self.case,
                "Check that Mrs Shaw says who she is and she is ready to chat.",
            ),
            "check_identity",
        )
        self.assertEqual(
            match_action_id(
                self.case,
                "Check identification and verify the patient's ID.",
            ),
            "check_identity",
        )

    def test_combined_action_and_words_can_identify_pain_assessment(self):
        self.assertEqual(
            match_action_id(
                self.case,
                "I discuss her pain. Could you tell me where it hurts and how severe it is from zero to ten?",
            ),
            "assess_pain",
        )

    def test_medication_history_question_does_not_complete_record_check(self):
        self.assertIsNone(
            match_action_id(
                self.case,
                "Check medication. I am going to see what medication you are on.",
            )
        )
        self.assertEqual(
            match_action_id(
                self.case,
                "Check the allergy record and prescription chart.",
            ),
            "check_allergies_and_prescription",
        )

    def test_unmatched_action_is_logged_without_clinical_change(self):
        original_state = deepcopy(self.session["state"])
        result = add_learner_action(self.case, self.session, "I will tidy the bedside table.")
        self.assertTrue(result.applied)
        self.assertEqual(self.session["state"]["elapsed_minutes"], 2)
        self.assertEqual(self.session["state"]["pain_score"], original_state["pain_score"])
        self.assertIsNone(self.session["action_log"][0]["action_id"])
        self.assertFalse(self.session["action_log"][0]["applied"])

    def test_supportive_unmatched_action_has_specific_transcript_cue(self):
        result = add_learner_action(
            self.case,
            self.session,
            "I introduce myself.",
            supportive=True,
        )
        self.assertTrue(result.applied)
        self.assertIn("supportive action", self.session["transcript"][-1]["text"])

    def test_ai_unmapped_action_helper_never_changes_authored_clinical_facts(self):
        original = deepcopy(self.session["state"])
        result = record_unmapped_action(
            self.case, self.session, "I adjust the pillows for comfort."
        )
        self.assertTrue(result.applied)
        self.assertEqual(self.session["state"]["pain_score"], original["pain_score"])
        self.assertEqual(self.session["action_log"][-1]["action_id"], None)

    def test_student_export_excludes_facilitator_notes(self):
        self.session["feedback_log"].append(
            {
                "rating": "appropriate",
                "feedback": "This interaction fits the authored pathway.",
            }
        )
        end_session(self.session)
        exported = student_export(self.case, self.session)
        self.assertNotIn("facilitator_only", exported)
        self.assertNotIn("state", exported)
        self.assertEqual(exported["status"], "ended")
        self.assertEqual(exported["practice_mode"], "coached")
        self.assertEqual(exported["formative_feedback"][0]["rating"], "appropriate")


if __name__ == "__main__":
    unittest.main()
