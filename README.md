# Nurse Simulation Studio

A first Streamlit prototype for supervised nursing-education rehearsal using
entirely fictional adult patients.

Clinical and consent state changes are deterministic and educator-authored.
An optional Gemini or OpenAI model can phrase synthetic-patient replies, but it
cannot change simulation state, provide medication doses or make competence
decisions. Authored dialogue remains the automatic fallback.

## Run locally

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Then open the local address printed by Streamlit, normally
`http://localhost:8501`.

## Optional AI dialogue

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, add a
`GEMINI_API_KEY`, an `OPENAI_API_KEY`, or both, and choose the provider in the
sidebar. Never commit the real secrets file. Without a configured key, the app
continues to use its authored replies.

## Test

```powershell
py -m unittest discover -s tests -v
py .\sample_patients\validate_cases.py
```

## Prototype features

- Four synthetic patient cases
- Patient library and learner briefs
- Authored nursing actions with prerequisite checks
- AI interpretation of natural-language actions with a 1–5 suitability range
- Combined action-and-dialogue submission with patient-state-aware formative feedback
- Deterministic time-triggered changes
- Optional AI-phrased patient dialogue with safe authored fallback replies
- Restartable sessions
- Facilitator-only view
- Structured debrief
- Learner-safe JSON export

The cases remain development fixtures until reviewed and approved through the
appropriate nursing-education and local clinical-governance processes.

Action suitability uses five educator-reviewable dimensions: patient-centredness,
effectiveness and relevance, safety and timing, consent and dignity, and
communication and professional trust. AI can score any proposed action, but it
can only change simulation state when it confidently maps an appropriate action
to one of the case's bounded, educator-authored transitions.
