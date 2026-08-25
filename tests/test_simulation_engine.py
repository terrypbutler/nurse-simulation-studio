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
    record_unmapped_action,
    student_export,
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

    def test_precondition_blocks_unsafe_action(self):
        result = apply_action(self.case, self.session, "administer_charted_option")
        self.assertFalse(result.applied)
        self.assertFalse(self.session["state"]["analgesia_administered"])
        self.assertEqual(self.session["state"]["elapsed_minutes"], 0)

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

    def test_unmatched_action_is_logged_without_clinical_change(self):
        original_state = deepcopy(self.session["state"])
        result = add_learner_action(self.case, self.session, "I will tidy the bedside table.")
        self.assertTrue(result.applied)
        self.assertEqual(self.session["state"]["elapsed_minutes"], 2)
        self.assertEqual(self.session["state"]["pain_score"], original_state["pain_score"])
        self.assertIsNone(self.session["action_log"][0]["action_id"])
        self.assertFalse(self.session["action_log"][0]["applied"])

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
        self.assertEqual(exported["formative_feedback"][0]["rating"], "appropriate")


if __name__ == "__main__":
    unittest.main()
