"""Educator-authored dialogue for the deterministic prototype.

Nothing in this module changes clinical state. The simulation engine owns all
state transitions; these lines only make the synthetic patient feel responsive.
"""

from __future__ import annotations


ACTION_RESPONSES: dict[str, dict[str, str]] = {
    "PAT-001": {
        "check_identity": "Of course. I'm Eleanor Shaw, and the details on my wristband are correct.",
        "assess_pain": (
            "It is about seven out of ten. It aches all the time and catches sharply "
            "when I try to move."
        ),
        "check_allergies_and_prescription": (
            "Mrs Shaw watches while you check the simulated records."
        ),
        "explain_analgesia": (
            "I was worried it might make me too sleepy when my daughter visits. "
            "If that concern is covered, I would consider it."
        ),
        "seek_consent": "Yes, I understand what you have explained and I would like to accept it.",
        "administer_charted_option": "Thank you. I hope it makes moving a little easier.",
        "reassess_pain": "It is nearer four now. It still hurts when I move, but it is more manageable.",
    },
    "PAT-002": {
        "check_identity": "David... David Morgan. Why am I in this room?",
        "measure_observations": "David becomes distracted while the observations are completed.",
        "check_baseline_cognition": "The authored handover confirms that this confusion is new.",
        "provide_orientation_support": "Thank you. I can see the clock now. You said I'm in hospital?",
        "request_senior_help": "David remains in view while the colleague acknowledges your request.",
        "escalate_urgent_concern": "The receiving clinician asks you to give a concise structured handover.",
    },
    "PAT-003": {
        "create_privacy": "Thank you. I didn't want everyone passing by to hear this.",
        "seek_discussion_permission": "Yes, we can talk about it now.",
        "explore_concerns": (
            "I'm most worried about it leaking when I'm out. I keep saying I'm fine, "
            "but I don't really know what I would do."
        ),
        "explain_in_chunks": "That was easier to follow when we took one part at a time.",
        "use_teach_back": (
            "I can explain the routine part, but I'm not sure who I should contact if "
            "something goes wrong."
        ),
        "seek_family_permission": "Yes, I would like my sister to join us for the final review.",
        "arrange_specialist_review": "That would reassure me before I go home.",
    },
    "PAT-004": {
        "reduce_noise": "That's much better. I can hear you when you face me like that.",
        "check_hearing_support": "Yes please—the left hearing aid feels loose.",
        "create_privacy": "Thank you for closing the door.",
        "check_preferences": "I can wash my face and upper body myself. I only need help lower down.",
        "seek_consent": "Yes, I agree to that amount of help.",
        "start_agreed_care": "All right, I'm ready to begin.",
        "pause_on_withdrawal": "Thank you for stopping. The water feels too cold; I need a moment.",
    },
}


OPENING_LINES: dict[str, str] = {
    "PAT-001": "It hurts more than I expected, but I don't want anything that will knock me out.",
    "PAT-002": "I was meant to be going home... Where is my coat?",
    "PAT-003": "They said I might go home today. I think I've understood everything.",
    "PAT-004": "Sorry, I didn't catch that—the television is quite loud.",
}


FREE_TEXT_RESPONSES: dict[str, tuple[str, ...]] = {
    "PAT-001": (
        "Can you explain what the next step would be?",
        "I want to be involved in the decision.",
    ),
    "PAT-002": (
        "I'm not sure. Could you say that one part at a time?",
        "David looks towards you, then becomes distracted by activity in the corridor.",
    ),
    "PAT-003": (
        "Could we take that slowly? I don't want to pretend I understand.",
        "Aisha listens, then glances at the folded leaflet.",
    ),
    "PAT-004": (
        "Please face me when you speak so I can follow you.",
        "Mr Chen waits for the background noise to settle before replying.",
    ),
}


# These educator-authored phrases connect free-text learner actions to the
# deterministic action IDs. They are deliberately kept out of the learner UI.
ACTION_PHRASES: dict[str, dict[str, tuple[str, ...]]] = {
    "PAT-001": {
        "check_identity": (
            "check identity", "confirm identity", "check wristband", "two identifiers"
        ),
        "assess_pain": (
            "assess pain", "ask about pain", "pain assessment", "pain score"
        ),
        "check_allergies_and_prescription": (
            "check allergies", "check allergy record", "check prescription",
            "check medication chart", "check medicine chart", "check drug chart",
        ),
        "explain_analgesia": (
            "explain analgesia", "explain pain relief", "discuss pain relief",
            "explain charted option", "invite questions",
        ),
        "seek_consent": (
            "seek consent", "ask for consent", "gain consent", "obtain consent",
            "ask if she accepts", "ask if she wants pain relief",
        ),
        "administer_charted_option": (
            "administer charted option", "administer analgesia", "give pain relief",
            "give analgesia", "record administration",
        ),
        "reassess_pain": (
            "reassess pain", "review pain", "check pain again", "recheck pain",
            "reassess comfort",
        ),
    },
    "PAT-002": {
        "check_identity": (
            "check identity", "confirm identity", "check wristband", "two identifiers"
        ),
        "measure_observations": (
            "measure observations", "take observations", "check observations",
            "check vital signs", "take vital signs", "complete observation set",
        ),
        "check_baseline_cognition": (
            "check baseline cognition", "establish baseline cognition",
            "review handover", "check if confusion is new", "usual cognition",
        ),
        "provide_orientation_support": (
            "provide orientation", "orientate patient", "orientation support",
            "show him the clock", "make glasses available", "reduce confusion",
        ),
        "request_senior_help": (
            "request senior help", "ask senior for help", "get senior help",
            "request immediate review", "ask registered colleague",
        ),
        "escalate_urgent_concern": (
            "escalate urgent concern", "urgent escalation", "escalate deterioration",
            "call emergency team", "use escalation pathway",
        ),
    },
    "PAT-003": {
        "create_privacy": (
            "create privacy", "provide privacy", "close the curtains", "private discussion"
        ),
        "seek_discussion_permission": (
            "ask permission to discuss", "seek permission to discuss",
            "ask if we can talk", "permission to talk",
        ),
        "explore_concerns": (
            "explore concerns", "ask about concerns", "ask what matters",
            "managing at home", "worries about home",
        ),
        "explain_in_chunks": (
            "explain in chunks", "one step at a time", "break down explanation",
            "explain care step",
        ),
        "use_teach_back": (
            "use teach back", "teach back", "explain in her own words",
            "repeat the plan", "check understanding",
        ),
        "seek_family_permission": (
            "ask about family involvement", "involve family", "family member involved",
            "seek family permission", "ask about her sister",
        ),
        "arrange_specialist_review": (
            "arrange specialist review", "request specialist review",
            "refer to stoma nurse", "specialist before discharge",
        ),
    },
    "PAT-004": {
        "reduce_noise": (
            "reduce noise", "turn down television", "turn off television",
            "reduce background noise", "face the patient",
        ),
        "check_hearing_support": (
            "check hearing aid", "help with hearing aid", "hearing support",
            "ask about hearing aid",
        ),
        "create_privacy": (
            "create privacy", "provide privacy", "close the door", "private care space"
        ),
        "check_preferences": (
            "check preferences", "ask his preferences", "ask what he can do",
            "ask what he wants to do", "independent care",
        ),
        "seek_consent": (
            "seek consent", "ask for consent", "gain consent", "obtain consent",
            "ask permission to help",
        ),
        "start_agreed_care": (
            "start agreed care", "begin agreed care", "start personal care",
            "provide agreed assistance", "help with lower body",
        ),
        "pause_on_withdrawal": (
            "stop care", "pause care", "withdraws consent", "withdrawal of consent",
            "ask what he needs",
        ),
    },
}


def action_response(case_id: str, action_id: str) -> str:
    """Return an authored response for an action, with a neutral fallback."""

    return ACTION_RESPONSES.get(case_id, {}).get(
        action_id,
        "The patient acknowledges the action without adding new clinical information.",
    )


def free_text_response(case_id: str, message_count: int) -> str:
    """Return a stable authored line without interpreting clinical content."""

    options = FREE_TEXT_RESPONSES.get(
        case_id,
        ("The patient listens and waits for the next clear question.",),
    )
    return options[message_count % len(options)]
