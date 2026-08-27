"""Deterministic state engine for synthetic nursing simulations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

from modules.scenario_repository import DEFAULT_LOCAL_LIBRARY, load_scenario_library
from modules.simulation_content import (
    action_phrases,
    action_response,
    free_text_response,
    opening_line,
)


DATA_PATH = DEFAULT_LOCAL_LIBRARY
PRACTICE_MODES = {"coached", "immersive"}


@dataclass(frozen=True)
class ActionResult:
    applied: bool
    message: str
    new_cues: tuple[str, ...] = ()
    fired_events: tuple[str, ...] = ()


def load_cases(path: Path | str = DATA_PATH, token: str = "") -> list[dict[str, Any]]:
    """Load validated cases from a local fallback or external HTTPS library."""

    return load_scenario_library(path, token=token)


def case_by_id(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise KeyError(f"Unknown case: {case_id}")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_session(
    case: dict[str, Any],
    learner_name: str = "Learner",
    practice_mode: str = "coached",
    start_in_prebrief: bool = False,
) -> dict[str, Any]:
    """Create a fresh session without mutating the case definition."""

    if practice_mode not in PRACTICE_MODES:
        raise ValueError(f"Unknown practice mode: {practice_mode}")
    state = deepcopy(case["initial_state"])
    state.setdefault("elapsed_minutes", 0)
    state.setdefault("revealed_cues", [])
    return {
        "case_id": case["case_id"],
        "learner_name": learner_name.strip() or "Learner",
        "started_at": utc_timestamp(),
        "status": "active",
        "phase": "prebrief" if start_in_prebrief else "active",
        "practice_mode": practice_mode,
        "state": state,
        "resolved_events": [],
        "transcript": [
            {
                "role": "patient",
                "speaker": case["patient"]["display_name"],
                "text": opening_line(case),
                "minute": 0,
            }
        ],
        "action_log": [],
        "feedback_log": [],
        "nursing_notes": [],
        "clinical_check_log": [],
        "generated_observations": {},
        "generated_observation_stage": None,
        "latest_patient_expression": {},
        "educator_rubric": deepcopy(case.get("educator_rubric", [])),
        "reflection": {},
    }


def start_session(session: dict[str, Any]) -> None:
    """Move a prebriefed session into the active encounter."""

    if session.get("status") == "active":
        session["phase"] = "active"


def _interaction_block(session: dict[str, Any]) -> str | None:
    if session.get("status") != "active":
        return "This simulation has ended. Restart it to continue."
    if session.get("phase", "active") != "active":
        return "Complete the prebrief before beginning the encounter."
    return None


def _conditions_met(state: dict[str, Any], conditions: dict[str, Any]) -> bool:
    return all(state.get(key) == expected for key, expected in conditions.items())


def _apply_effects(state: dict[str, Any], effects: dict[str, Any]) -> None:
    for key, value in effects.items():
        if key.endswith("_delta"):
            target = key[: -len("_delta")]
            state[target] = state.get(target, 0) + value
        else:
            state[key] = value

    for bounded in (
        "trust",
        "understanding_level",
        "overload_level",
        "fatigue_level",
        "confusion_level",
        "anxiety_level",
        "pain_score",
    ):
        if bounded in state and isinstance(state[bounded], (int, float)):
            state[bounded] = max(0, min(100 if bounded == "trust" else 10, state[bounded]))


def _resolve_due_events(case: dict[str, Any], session: dict[str, Any]) -> tuple[str, ...]:
    fired: list[str] = []
    elapsed = session["state"]["elapsed_minutes"]
    resolved = set(session["resolved_events"])

    for event in case["time_events"]:
        event_id = event["event_id"]
        if event_id in resolved or event["at_minute"] > elapsed:
            continue

        if not _conditions_met(session["state"], event["when"]):
            continue

        _apply_effects(session["state"], event["effects"])
        cue = event["visible_cue"]
        session["state"]["revealed_cues"].append(cue)
        session["transcript"].append(
            {
                "role": "cue",
                "speaker": "Visible change",
                "text": cue,
                "minute": elapsed,
            }
        )
        fired.append(event_id)
        session["resolved_events"].append(event_id)
        resolved.add(event_id)

    return tuple(fired)


def _find_action(case: dict[str, Any], action_id: str) -> dict[str, Any]:
    for action in case["allowed_actions"]:
        if action["action_id"] == action_id:
            return action
    raise KeyError(f"Unknown action for {case['case_id']}: {action_id}")


def clinical_check_block(case: dict[str, Any], session: dict[str, Any]) -> str | None:
    """Apply an authored full-observation prerequisite to individual checks too."""

    observation_action = next(
        (
            action
            for action in case["allowed_actions"]
            if action["action_id"] == "measure_observations"
        ),
        None,
    )
    if observation_action and not _conditions_met(
        session["state"], observation_action["preconditions"]
    ):
        return observation_action.get(
            "blocked_message",
            "The required earlier step has not been completed.",
        )
    return None


def _normalise_action_text(text: str) -> tuple[str, set[str]]:
    normalised = " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
    return normalised, set(normalised.split())


def match_action_id(case: dict[str, Any], text: str) -> str | None:
    """Match learner wording to one educator-authored action, if unambiguous."""

    normalised, words = _normalise_action_text(text)
    allowed_ids = {action["action_id"] for action in case["allowed_actions"]}
    candidates: list[tuple[int, str]] = []

    for action_id, phrases in action_phrases(case).items():
        if action_id not in allowed_ids:
            continue
        best_score = 0
        for phrase in phrases:
            phrase_normalised, phrase_words = _normalise_action_text(phrase)
            if phrase_normalised in normalised or phrase_words <= words:
                best_score = max(best_score, len(phrase_words))
        if best_score:
            candidates.append((best_score, action_id))

    if not candidates:
        return None
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        return None
    return candidates[0][1]


def apply_action(
    case: dict[str, Any],
    session: dict[str, Any],
    action_id: str,
    minutes: int = 2,
    learner_text: str | None = None,
) -> ActionResult:
    """Apply one authored action and then resolve time-based events."""

    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)

    action = _find_action(case, action_id)
    if not _conditions_met(session["state"], action["preconditions"]):
        return ActionResult(
            False,
            action.get("blocked_message", "The required earlier step has not been completed."),
        )

    _apply_effects(session["state"], action["effects"])
    new_cues = tuple(action.get("reveals", []))
    session["state"]["revealed_cues"].extend(new_cues)
    session["state"]["elapsed_minutes"] += max(0, minutes)

    response = action_response(case, action_id)
    session["transcript"].append(
        {
            "role": "learner_action",
            "speaker": session["learner_name"],
            "text": learner_text or action["label"],
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    session["transcript"].append(
        {
            "role": "patient",
            "speaker": case["patient"]["display_name"],
            "text": response,
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    session["action_log"].append(
        {
            "action_id": action_id,
            "label": action["label"],
            "minute": session["state"]["elapsed_minutes"],
            "applied": True,
        }
    )
    fired = _resolve_due_events(case, session)
    return ActionResult(True, response, new_cues, fired)


def add_learner_action(
    case: dict[str, Any], session: dict[str, Any], text: str, minutes: int = 2
) -> ActionResult:
    """Interpret a free-text action without exposing the authored action menu."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return ActionResult(False, "Describe one nursing action first.")
    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)

    action_id = match_action_id(case, clean)
    if action_id is not None:
        return apply_action(case, session, action_id, minutes, learner_text=clean)

    return record_unmapped_action(case, session, clean, minutes)


def record_unmapped_action(
    case: dict[str, Any], session: dict[str, Any], text: str, minutes: int = 2
) -> ActionResult:
    """Record an action that has no safe deterministic state transition."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return ActionResult(False, "Describe one nursing action first.")
    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)
    session["state"]["elapsed_minutes"] += max(0, minutes)
    session["transcript"].append(
        {
            "role": "learner_action",
            "speaker": session["learner_name"],
            "text": clean,
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    session["transcript"].append(
        {
            "role": "cue",
            "speaker": "Scenario response",
            "text": "No new clinical information is revealed by that action.",
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    session["action_log"].append(
        {
            "action_id": None,
            "label": clean,
            "minute": session["state"]["elapsed_minutes"],
            "applied": False,
        }
    )
    fired = _resolve_due_events(case, session)
    return ActionResult(True, "The action was recorded without changing clinical facts.", (), fired)


def add_learner_dialogue(
    case: dict[str, Any],
    session: dict[str, Any],
    text: str,
    minutes: int = 1,
    reply_text: str | None = None,
) -> ActionResult:
    """Add free text and an authored neutral reply; do not change clinical facts."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return ActionResult(False, "Enter something to say first.")
    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)

    prior_messages = sum(1 for item in session["transcript"] if item["role"] == "learner_dialogue")
    session["state"]["elapsed_minutes"] += max(0, minutes)
    session["transcript"].append(
        {
            "role": "learner_dialogue",
            "speaker": session["learner_name"],
            "text": clean,
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    reply = reply_text or free_text_response(case, prior_messages)
    session["transcript"].append(
        {
            "role": "patient",
            "speaker": case["patient"]["display_name"],
            "text": reply,
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    fired = _resolve_due_events(case, session)
    return ActionResult(True, reply, (), fired)


def record_learner_dialogue(
    case: dict[str, Any], session: dict[str, Any], text: str, minutes: int = 1
) -> ActionResult:
    """Record learner speech without creating a patient reply."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return ActionResult(False, "Enter something to say first.")
    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)

    session["state"]["elapsed_minutes"] += max(0, minutes)
    session["transcript"].append(
        {
            "role": "learner_dialogue",
            "speaker": session["learner_name"],
            "text": clean,
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    fired = _resolve_due_events(case, session)
    return ActionResult(True, "Dialogue recorded.", (), fired)


def record_clinical_check(
    case: dict[str, Any],
    session: dict[str, Any],
    learner_text: str,
    result_text: str,
    check_ids: tuple[str, ...],
    *,
    minutes: int = 2,
    generated: bool = False,
    record_learner_action: bool = True,
) -> ActionResult:
    """Record bounded fictional observations without placing AI in the state engine."""

    clean_action = " ".join(learner_text.split())[:600]
    clean_result = " ".join(result_text.split())[:1000]
    if not clean_action or not clean_result or not check_ids:
        return ActionResult(False, "No supported clinical check was completed.")
    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)
    session["state"]["elapsed_minutes"] += max(0, minutes)
    if record_learner_action:
        session["transcript"].append(
            {
                "role": "learner_action",
                "speaker": session["learner_name"],
                "text": clean_action,
                "minute": session["state"]["elapsed_minutes"],
            }
        )
    session["transcript"].append(
        {
            "role": "cue",
            "speaker": "Fictional observation result",
            "text": clean_result,
            "minute": session["state"]["elapsed_minutes"],
            "source": "bounded_ai" if generated else "authored_baseline",
        }
    )
    session.setdefault("clinical_check_log", []).append(
        {
            "checks": list(check_ids),
            "result": clean_result,
            "minute": session["state"]["elapsed_minutes"],
            "source": "bounded_ai" if generated else "authored_baseline",
        }
    )
    fired = _resolve_due_events(case, session)
    return ActionResult(True, clean_result, (), fired)


def record_nursing_note(
    case: dict[str, Any], session: dict[str, Any], text: str, minutes: int = 1
) -> ActionResult:
    """Record learner documentation and allow authored time events to progress."""

    clean = " ".join(text.split())[:1000]
    if not clean:
        return ActionResult(False, "Write a short nursing note first.")
    if blocked := _interaction_block(session):
        return ActionResult(False, blocked)

    session["state"]["elapsed_minutes"] += max(0, minutes)
    entry = {
        "minute": session["state"]["elapsed_minutes"],
        "author": session["learner_name"],
        "text": clean,
    }
    session.setdefault("nursing_notes", []).append(entry)
    session["transcript"].append(
        {
            "role": "documentation",
            "speaker": session["learner_name"],
            "text": clean,
            "minute": session["state"]["elapsed_minutes"],
        }
    )
    fired = _resolve_due_events(case, session)
    return ActionResult(True, "Nursing note saved.", (), fired)


def append_patient_response(
    case: dict[str, Any],
    session: dict[str, Any],
    text: str,
    nonverbal_cue: str = "",
    response_latency: str = "immediate",
) -> bool:
    """Append patient wording without changing deterministic state."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return False
    cue = " ".join(nonverbal_cue.split())[:300]
    if cue:
        session["transcript"].append(
            {
                "role": "nonverbal",
                "speaker": "Observed behaviour",
                "text": cue,
                "minute": session["state"]["elapsed_minutes"],
            }
        )
    session["transcript"].append(
        {
            "role": "patient",
            "speaker": case["patient"]["display_name"],
            "text": clean,
            "minute": session["state"]["elapsed_minutes"],
            "response_latency": response_latency,
        }
    )
    session["latest_patient_expression"] = {
        "nonverbal_cue": cue,
        "response_latency": response_latency,
    }
    return True


def remove_latest_patient_response(session: dict[str, Any]) -> str | None:
    """Remove the latest patient wording so a combined reply can replace it."""

    for index in range(len(session["transcript"]) - 1, -1, -1):
        if session["transcript"][index]["role"] == "patient":
            return str(session["transcript"].pop(index)["text"])
    return None


def replace_latest_patient_response(session: dict[str, Any], text: str) -> bool:
    """Replace only the latest patient wording; never alter clinical state."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return False
    for item in reversed(session["transcript"]):
        if item["role"] == "patient":
            item["text"] = clean
            return True
    return False


def end_session(session: dict[str, Any]) -> None:
    session["status"] = "ended"
    session["phase"] = "debrief"
    session["ended_at"] = utc_timestamp()


def student_export(case: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    """Return a learner-safe export that excludes facilitator-only content."""

    return {
        "case_id": case["case_id"],
        "case_title": case["title"],
        "synthetic_data_notice": case["synthetic_data_notice"],
        "learner_name": session["learner_name"],
        "practice_mode": session.get("practice_mode", "coached"),
        "status": session["status"],
        "started_at": session["started_at"],
        "ended_at": session.get("ended_at"),
        "elapsed_minutes": session["state"]["elapsed_minutes"],
        "transcript": deepcopy(session["transcript"]),
        "actions": deepcopy(session["action_log"]),
        "nursing_notes": deepcopy(session.get("nursing_notes", [])),
        "clinical_checks": deepcopy(session.get("clinical_check_log", [])),
        "formative_feedback": deepcopy(session.get("feedback_log", [])),
        "reflection": deepcopy(session.get("reflection", {})),
    }
