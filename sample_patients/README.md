# Synthetic patient sample pack

This folder contains four fictional adult-nursing cases for prototyping the
nursing adaptation of the Butler Academy application. No record is based on a
real person.

## Cases

| ID | Scenario | Main practice focus |
| --- | --- | --- |
| `PAT-001` | Postoperative pain | Pain assessment, medicine explanation, consent/refusal and reassessment |
| `PAT-002` | Acute confusion with deterioration | Observation, recognition of change and timely escalation |
| `PAT-003` | New-stoma discharge conversation | Health literacy, teach-back, dignity and discharge understanding |
| `PAT-004` | Personal care with hearing impairment | Accessible communication, privacy and withdrawal of consent |

The cases deliberately use a narrow adult-nursing scope. Medication entries
refer to an educator-approved simulated prescription chart; the data does not
contain a dose and the dialogue model must never invent one.

## Files

- `patient_cases.json` contains the sample cases.
- `patient_case.schema.json` documents and validates their core structure.
- `validate_cases.py` performs additional safety checks without third-party
  dependencies.

Run the checks from this folder with:

```powershell
py .\validate_cases.py
```

## Suggested application behaviour

1. Load a case and copy `initial_state` into session state.
2. Display only `patient`, `clinical.visible_at_start` and cues that the
   deterministic engine has revealed.
3. Accept only an action ID listed in `allowed_actions` or free-text dialogue.
4. Apply time events and action effects in application code, never in the AI
   model.
5. Give the AI only `ai_contract.allowed_context`, the currently revealed
   clinical state and the student's exact words.
6. Keep `facilitator_only` out of every AI request and student-facing export.
7. Use the debrief prompts with a prepared educator; do not turn them into an
   automatic competence decision.

These samples are development fixtures, not validated curricula or clinical
guidance. A nursing educator and the organisation's simulation, medicines,
information-governance and accessibility leads should approve cases before
student use.
