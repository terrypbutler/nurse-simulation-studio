# Nurse Simulation Studio

A first Streamlit prototype for supervised nursing-education rehearsal using
entirely fictional adult patients.

Clinical and consent state changes are deterministic and educator-authored.
The prototype does not call an AI model, invent physiology, provide medication
doses or make competence decisions.

## Run locally

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Then open the local address printed by Streamlit, normally
`http://localhost:8501`.

## Test

```powershell
py -m unittest discover -s tests -v
py .\sample_patients\validate_cases.py
```

## Prototype features

- Four synthetic patient cases
- Patient library and learner briefs
- Authored nursing actions with prerequisite checks
- Deterministic time-triggered changes
- Authored patient dialogue and safe free-text fallback replies
- Restartable sessions
- Facilitator-only view
- Structured debrief
- Learner-safe JSON export

The cases remain development fixtures until reviewed and approved through the
appropriate nursing-education and local clinical-governance processes.
