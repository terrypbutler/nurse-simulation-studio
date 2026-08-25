# Nurse Simulation Studio

A first Streamlit prototype for supervised nursing-education rehearsal using
entirely fictional adult patients.

Clinical, consent and persistent patient-experience changes are deterministic
and educator-authored. An optional Gemini or OpenAI model interprets the
learner's proposed action and spoken words, then phrases a synthetic-patient
reply and bounded non-verbal cue. It cannot change simulation state, provide
medication doses or make competence decisions. Authored dialogue and behaviour
remain the automatic fallback.

## Run locally

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Then open the local address printed by Streamlit, normally
`http://localhost:8501`.

## Optional AI interactions

Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, add a
`GEMINI_API_KEY`, an `OPENAI_API_KEY`, or both, and choose the provider in the
sidebar. Never commit the real secrets file. Without a configured key, the app
continues to use authored matching, replies and non-verbal cues.

OpenAI requests use the Responses API with strict JSON Schema outputs and
`store=False`. Do not use identifiable patient information: every included case
is synthetic, and local information-governance approval is still required.

## Test

```powershell
py -m unittest discover -s tests -v
py .\sample_patients\validate_cases.py
```

## Prototype features

- Four synthetic patient cases
- Patient library, learner briefs and scenario-specific prebriefs
- Coached mode with immediate feedback and immersive mode with delayed feedback
- A clinical workspace for handover, observations, records, environment and notes
- Free-text nursing actions with educator-authored prerequisite checks
- AI interpretation of natural-language actions with a 1–5 suitability range
- Direct, supportive, tangential, unclear and counterproductive relevance bands
- Combined action-and-dialogue submission with patient-state-aware formative feedback
- Richer bounded state for trust, emotion, fatigue, overload, understanding,
  confusion, dignity and consent
- Deterministic, condition-aware time consequences
- Natural patient dialogue, response latency and educator-authored non-verbal cues
- Restartable sessions
- Facilitator-only view
- Structured reactions–analysis–summary debrief
- Editable case-specific educator rubrics and evidence notes
- Learner-safe JSON export

The cases remain development fixtures until reviewed and approved through the
appropriate nursing-education and local clinical-governance processes.

Action suitability uses five educator-reviewable dimensions: patient-centredness,
effectiveness and relevance, safety and timing, consent and dignity, and
communication and professional trust. AI can score any proposed action, but it
can only change simulation state when it confidently maps an appropriate action
to one of the case's bounded, educator-authored transitions.

## Educational review before use

The app now includes a quality-review template in `QUALITY_REVIEW.md`. Before
student use, each case should be reviewed by nursing educators, relevant clinical
specialists, people with lived experience, accessibility and inclusion reviewers,
and information-governance leads. Pilot with both novice and experienced users,
then compare facilitator judgements with the AI-supported interaction feedback.
