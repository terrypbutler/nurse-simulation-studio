# Authenticity and quality review

Use this checklist before a synthetic case is used with students. Record names,
dates, decisions and required changes in the organisation's approved review system.
This file is a development aid, not evidence of approval.

## 1. Clinical and educational review

- Confirm the encounter, priorities, time course and escalation placeholders are
  plausible for the intended setting and learner level.
- Confirm every deterministic state change, prerequisite, consequence and visible
  cue is educator-authored and locally appropriate.
- Confirm learning outcomes, prebrief, fidelity limitations, facilitation plan and
  debrief prompts are aligned.
- Confirm the case cannot be mistaken for clinical guidance, a medicine reference
  or an automatic competence assessment.

## 2. Patient authenticity and lived experience

- Review the patient's goals, concerns, language, hesitations, refusals and
  non-verbal palette with an appropriate lived-experience reviewer.
- Remove stereotypes, unnecessary demographic cues and behaviour that exists only
  to make the learner's task easier.
- Check that communication needs affect access without being treated as evidence of
  cognition, capacity or compliance.
- Check that the patient sometimes gives incomplete, uncertain or misunderstood
  answers in a way that remains consistent and humane.

## 3. Accessibility, equality and inclusion

- Test keyboard-only use, focus order, labels, contrast, zoom and screen-reader
  announcements.
- Review language load, reading level and whether time pressure unfairly penalises
  learners using assistive technology or communicating in an additional language.
- Review names, identities, family structures, disability, age, culture and faith
  for representational balance and stereotype risk.
- Provide a supported way to pause, opt out and re-enter learning after distress.

## 4. AI and information governance

- Use synthetic data only. Never paste real patient or learner-identifiable clinical
  information into the scenario.
- Confirm provider, region, retention, access controls, contracts and local DPIA or
  equivalent requirements before enabling an API.
- Confirm AI receives only the allow-listed revealed state and cannot mutate facts,
  consent, observations, treatment effects or event timing.
- Test malformed output, provider failure, unsafe dose generation, prompt injection,
  hallucinated facts and authored fallback behaviour.

## 5. Pilot and calibration

- Run think-aloud pilots with novice learners, experienced learners and at least two
  facilitators.
- Use a shared sample of interactions to compare facilitator ratings with each other
  and with AI-supported scores. Investigate systematic disagreement rather than
  treating the AI rating as ground truth.
- Test direct, supportive, tangential, ambiguous and unsafe actions, including
  reasonable actions outside the deterministic pathway.
- Review whether coached mode helps learning and whether immersive mode withholds
  only coaching—not information the learner would realistically perceive.

## 6. Release decision

Record:

- Case version and owner
- Intended learners, setting and supervision level
- Reviewers and perspectives represented
- Known limitations and mitigations
- Approval decision and review date
- Evidence that required changes were retested
