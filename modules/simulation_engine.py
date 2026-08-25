"""Deterministic state engine for synthetic nursing simulations."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

from modules.simulation_content import (
    ACTION_PHRASES,
    OPENING_LINES,
    action_response,
    free_text_response,
)


DATA_PATH = Path(__file__).resolve().parents[1] / "sample_patients" / "patient_cases.json"


@dataclass(frozen=True)
class ActionResult:
    applied: bool
    message: str
    new_cues: tuple[str, ...] = ()
    fired_events: tuple[str, ...] = ()


def load_cases(path: Path = DATA_PATH) -> list[dict[str, Any]]:
    """Load the immutable authored case definitions."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["cases"]


def case_by_id(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    for case in cases:
        if case["case_id"] == case_id:
            return case
    raise KeyError(f"Unknown case: {case_id}")


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_session(case: dict[str, Any], learner_name: str = "Learner") -> dict[str, Any]:
    """Create a fresh session without mutating the case definition."""

    state = deepcopy(case["initial_state"])
    state.setdefault("elapsed_minutes", 0)
    state.setdefault("revealed_cues", [])
    return {
        "case_id": case["case_id"],
        "learner_name": learner_name.strip() or "Learner",
        "started_at": utc_timestamp(),
        "status": "active",
        "state": state,
        "resolved_events": [],
        "transcript": [
            {
                "role": "patient",
                "speaker": case["patient"]["display_name"],
                "text": OPENING_LINES.get(case["case_id"], "The patient waits to speak with you."),
                "minute": 0,
            }
        ],
        "action_log": [],
        "reflection": {},
    }


def _conditions_met(state: dict[str, Any], conditions: dict[str, Any]) -> bool:
    return all(state.get(key) == expected for key, expected in conditions.items())


def _apply_effects(state: dict[str, Any], effects: dict[str, Any]) -> None:
    for key, value in effects.items():
        if key.endswith("_delta"):
            target = key[: -len("_delta")]
            state[target] = state.get(target, 0) + value
        else:
            state[key] = value

    for bounded in ("trust", "understanding_level", "overload_level", "pain_score"):
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

        if _conditions_met(session["state"], event["when"]):
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


def _normalise_action_text(text: str) -> tuple[str, set[str]]:
    normalised = " ".join(re.findall(r"[a-z0-9]+", text.casefold()))
    return normalised, set(normalised.split())


def match_action_id(case: dict[str, Any], text: str) -> str | None:
    """Match learner wording to one educator-authored action, if unambiguous."""

    normalised, words = _normalise_action_text(text)
    allowed_ids = {action["action_id"] for action in case["allowed_actions"]}
    candidates: list[tuple[int, str]] = []

    for action_id, phrases in ACTION_PHRASES.get(case["case_id"], {}).items():
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

    if session.get("status") != "active":
        return ActionResult(False, "This simulation has ended. Restart it to continue.")

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

    response = action_response(case["case_id"], action_id)
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
    if session.get("status") != "active":
        return ActionResult(False, "This simulation has ended. Restart it to continue.")

    action_id = match_action_id(case, clean)
    if action_id is not None:
        return apply_action(case, session, action_id, minutes, learner_text=clean)

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
    case: dict[str, Any], session: dict[str, Any], text: str, minutes: int = 1
) -> ActionResult:
    """Add free text and an authored neutral reply; do not change clinical facts."""

    clean = " ".join(text.split())[:600]
    if not clean:
        return ActionResult(False, "Enter something to say first.")
    if session.get("status") != "active":
        return ActionResult(False, "This simulation has ended. Restart it to continue.")

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
    reply = free_text_response(case["case_id"], prior_messages)
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


def end_session(session: dict[str, Any]) -> None:
    session["status"] = "ended"
    session["ended_at"] = utc_timestamp()


def student_export(case: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    """Return a learner-safe export that excludes facilitator-only content."""

    return {
        "case_id": case["case_id"],
        "case_title": case["title"],
        "synthetic_data_notice": case["synthetic_data_notice"],
        "learner_name": session["learner_name"],
        "status": session["status"],
        "started_at": session["started_at"],
        "ended_at": session.get("ended_at"),
        "elapsed_minutes": session["state"]["elapsed_minutes"],
        "transcript": deepcopy(session["transcript"]),
        "actions": deepcopy(session["action_log"]),
        "reflection": deepcopy(session.get("reflection", {})),
    }
