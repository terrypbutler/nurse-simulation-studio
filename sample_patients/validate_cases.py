"""Validate the synthetic patient fixtures without external dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "patient_cases.json"
CASE_ID = re.compile(r"^PAT-\d{3}$")

REQUIRED_CASE_KEYS = {
    "case_id",
    "title",
    "synthetic_data_notice",
    "field",
    "setting",
    "patient",
    "learning",
    "prebrief",
    "clinical",
    "clinical_workspace",
    "initial_state",
    "time_events",
    "allowed_actions",
    "ai_contract",
    "facilitator_only",
    "educator_rubric",
    "debrief",
}

FORBIDDEN_IDENTITY_KEYS = {
    "date_of_birth",
    "dob",
    "nhs_number",
    "hospital_number",
    "address",
    "postcode",
}

REQUIRED_AI_PROHIBITIONS = {
    "observations",
    "diagnosis",
    "treatment",
    "judgement",
}


def words(items: list[str]) -> str:
    return " ".join(items).casefold()


def validate() -> list[str]:
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    errors: list[str] = []

    if data.get("schema_version") != "0.2.0":
        errors.append("schema_version must be 0.2.0")

    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        return errors + ["cases must be a non-empty list"]

    seen_ids: set[str] = set()
    for index, case in enumerate(cases, start=1):
        prefix = f"case {index}"
        missing = REQUIRED_CASE_KEYS - set(case)
        if missing:
            errors.append(f"{prefix}: missing keys {sorted(missing)}")

        case_id = case.get("case_id", "")
        if not CASE_ID.fullmatch(case_id):
            errors.append(f"{prefix}: invalid case_id {case_id!r}")
        if case_id in seen_ids:
            errors.append(f"{prefix}: duplicate case_id {case_id}")
        seen_ids.add(case_id)
        prefix = case_id or prefix

        if case.get("synthetic_data_notice") != "Entirely fictional training case":
            errors.append(f"{prefix}: synthetic-data notice is missing or changed")

        patient_keys = {str(key).casefold() for key in case.get("patient", {})}
        forbidden = patient_keys & FORBIDDEN_IDENTITY_KEYS
        if forbidden:
            errors.append(f"{prefix}: forbidden direct-identity keys {sorted(forbidden)}")
        if not case.get("patient", {}).get("nonverbal_palette"):
            errors.append(f"{prefix}: patient needs an educator-authored nonverbal palette")

        prebrief = case.get("prebrief", {})
        for key in ("role", "orientation", "resources", "limitations", "ground_rules"):
            if not prebrief.get(key):
                errors.append(f"{prefix}: prebrief is missing {key!r}")

        workspace = case.get("clinical_workspace", {})
        for key in ("handover", "environment", "available_resources", "record_access"):
            if key not in workspace:
                errors.append(f"{prefix}: clinical workspace is missing {key!r}")

        actions = case.get("allowed_actions", [])
        action_ids = [action.get("action_id") for action in actions]
        if len(action_ids) != len(set(action_ids)):
            errors.append(f"{prefix}: action IDs must be unique")

        for item in case.get("clinical", {}).get("prescribed_items", []):
            if set(item) != {"order_id", "display_text", "dose_source"}:
                errors.append(f"{prefix}: prescription fixtures may not contain dose fields")
            if "simulated prescription chart" not in item.get("dose_source", "").casefold():
                errors.append(f"{prefix}: dose_source must point to the simulated prescription chart")

        prohibited_text = words(case.get("ai_contract", {}).get("must_not_generate", []))
        for concept in REQUIRED_AI_PROHIBITIONS:
            if concept not in prohibited_text:
                errors.append(f"{prefix}: AI prohibition does not mention {concept!r}")

        allowed_state_keys = case.get("ai_contract", {}).get("allowed_state_keys", [])
        unknown_state_keys = set(allowed_state_keys) - set(case.get("initial_state", {}))
        if unknown_state_keys:
            errors.append(
                f"{prefix}: AI contract references unknown state keys {sorted(unknown_state_keys)}"
            )

        rubric = case.get("educator_rubric", [])
        rubric_ids = [item.get("criterion_id") for item in rubric]
        if len(rubric) < 3 or len(rubric_ids) != len(set(rubric_ids)):
            errors.append(f"{prefix}: educator rubric needs at least 3 unique criteria")

        if case.get("debrief", {}).get("automatic_competence_decision") is not False:
            errors.append(f"{prefix}: automatic competence decisions must be disabled")

    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        print("Validation failed:")
        for problem in problems:
            print(f"- {problem}")
        raise SystemExit(1)
    print("Validated 4 synthetic cases (schema 0.2.0) with no fixture safety errors.")
