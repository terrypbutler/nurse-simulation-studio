# Nurse Simulation Studio

This is the canonical nursing simulator. The earlier `nursing-app` repository
is retained only as a migration source and should not be used for new releases.

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
- Dialogue-only progression for conversational actions, with bounded multi-action recognition
- Combined action-and-speech concept matching and intent-specific replies in authored fallback mode
- Semantic action recognition separated from formative quality scoring
- Scrollable live transcript beside the interaction controls
- Explicit action descriptions retained for observations, administration, escalation and hands-on care
- Patient-specific fictional observations generated within validated bounds around an authored baseline
- Stable observation results within each deterministic patient stage, with authored fallback on failure
- Direct, supportive, tangential, unclear and counterproductive relevance bands
- Combined action-and-dialogue submission with patient-state-aware formative feedback
- Richer bounded state for trust, emotion, fatigue, overload, understanding,
  confusion, dignity and consent
- Deterministic, condition-aware time consequences
- Natural patient dialogue, response latency and educator-authored non-verbal cues
- Durable fact and conversation-move memory with recent-reply repetition checks
- Quote-linked evidence for each case-specific educator criterion
- Debrief aggregation showing demonstrated, partial, concerning and absent evidence
- Restartable sessions
- Facilitator-only view
- Structured reactions–analysis–summary debrief
- Editable case-specific educator rubrics and evidence notes
- Learner-safe JSON export
- Independently published, validated scenario library
- Portable prebriefs, workspaces, rubrics, dialogue facts and action matching
- Five-minute scenario cache with a manual refresh and bundled safe fallback
- Password-protected conversational editor that turns educator briefs into validated drafts
- Validated download and one-click publishing to the shared scenario library

The cases remain development fixtures until reviewed and approved through the
appropriate nursing-education and local clinical-governance processes.

## External scenario library

Add the published fictional library to local or Streamlit Community Cloud
secrets:

```toml
SCENARIO_LIBRARY_URL = "https://terrypbutler.github.io/nursing-scenario-library/library.json"
```

The Studio accepts HTTPS JSON only, limits its size, validates every scenario
and falls back to its bundled development cases if the external library is
unavailable or unsafe. New scenario content is authored in the separate
`nursing-scenario-library` repository rather than in this application.

## Edit shared scenarios in the Studio

The **Scenario editor** page lets an authorised educator describe a new learning
encounter—or changes to an existing one—in ordinary language. It asks about the
fictional patient, learning purpose, opening situation, expected learner actions,
timed consequences and debrief. The selected AI provider turns those answers
into the complete Studio format, validates it, shows an educator-readable
summary and accepts further plain-language revisions. Technical JSON is hidden
in an optional review panel, and the original structured editor remains
available for advanced users.

AI output is always marked as a development draft. Structural validation is not
clinical approval: an educator must review every fact, prerequisite, state
transition, patient response and debrief item before publishing or use.

One-click publishing writes the validated scenario into the source
`scenarios/` directory of `nursing-scenario-library`. That repository's existing
GitHub workflow performs its full schema checks, rebuilds `library.json` and
publishes it through GitHub Pages. Add these server-side secrets locally or in
Streamlit Community Cloud:

```toml
SCENARIO_EDITOR_PASSWORD = "a-long-password-shared-only-with-editors"
SCENARIO_GITHUB_REPOSITORY = "terrypbutler/nursing-scenario-library"
SCENARIO_GITHUB_BRANCH = "main"
SCENARIO_GITHUB_DIRECTORY = "scenarios"
SCENARIO_GITHUB_TOKEN = "a-fine-grained-token-with-contents-write-access"
```

The token needs write access to repository contents. Never commit the real
token or password. Learners and public visitors need neither value. After the
library workflow finishes, use **Refresh scenario library** to bypass the
Studio's five-minute cache.

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
