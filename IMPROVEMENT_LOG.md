# Nurse Simulation Studio improvement log

## 2026-08-28 — UX, educational validity and accessibility review

Status: Review complete; implementation deferred until credits are available.

### Review evidence

- Tested the running Streamlit app on desktop and at a 390 × 844 mobile viewport.
- Exercised the home page, patient library, prebrief, coached simulation, interaction feedback, simulation completion and structured debrief.
- Ran all 55 automated tests successfully.
- Validated all four bundled portable scenarios successfully.
- Found no browser console warnings or errors during the review.

### P0 — Correct false-negative interaction scoring

Implementation update, 2026-08-28: **Completed for the authored fallback path.**
The matcher now considers action and spoken wording together, recognises narrow
clinical concepts and common identity variants, keeps explicit-action safeguards,
uses intent-specific offline replies, and leaves unmatched turns unscored. The
supplied introduction, identification and medication transcript is covered by
automated and browser-level regression checks.

Additional implementation update, 2026-08-28: blocked or out-of-sequence
attempts now advance scenario time without applying unsafe effects. Encounters
end automatically at their authored duration, and the debrief records completed,
blocked and unreached pathway steps for discussion rather than allowing the
simulation to loop indefinitely. Three consecutive attempts at the same blocked
step now move directly to debrief.

A clinically sensible turn was tested with both fields completed:

- Action: “I introduce myself, confirm how Mrs Shaw would like to be addressed, and ask permission to discuss her pain.”
- Words: “Hello Mrs Shaw, I’m Terry, a student nurse. Is it okay if we talk about your pain? Could you tell me where it hurts and how severe it is from zero to ten?”

In authored-fallback mode, the app returned **3/5 — Mixed or unclear**, said the interaction could not be matched, and later marked **Person-centred pain assessment — Not evidenced** in the debrief.

Likely cause: when an action description is present, the fallback path attempts to match that field alone. Spoken words are only used for deterministic action matching when the action field is empty (`app.py`, approximately lines 782–836). The numerical fallback then assigns an unmatched or assessed-only interaction 3/5 (`app.py`, approximately lines 891–920).

Recommended change:

- Match the combined action and dialogue text for conversational actions.
- Continue requiring explicit action-box descriptions for observations, administration, escalation and hands-on care.
- When no confident match exists, show **Not automatically scored — facilitator review needed** rather than assigning a numerical 3/5.
- Ensure an unscored turn is not reported as criterion evidence being absent when the learner’s exact words contain relevant evidence.

### P0 — Protect facilitator-only information

The sidebar’s **Facilitator mode** switch can be enabled by any learner without authentication (`app.py`, approximately line 1674). It exposes the internal authored state and expected safety points (`app.py`, approximately lines 433–438).

Recommended change:

- Gate facilitator mode behind the existing educator authentication, a facilitator PIN, or a separate facilitator deployment.
- Hide facilitator controls in learner sessions rather than relying on an honour system.
- Consider hiding the Scenario editor navigation item from learner sessions as well, even though editing itself is password-protected.

### P0 — Prevent accidental session loss

The patient and practice-style controls remain editable during an active or completed encounter. Changing either causes `ensure_session` to replace the current session without an explicit confirmation (`app.py`, approximately lines 263–277).

Recommended change:

- Lock patient, practice style and learner identity after the prebrief begins.
- Add an explicit **End and choose another case** or **Start a new case** workflow.
- Warn before discarding an active session and offer an export first.

### P1 — Improve the narrow-screen simulation layout

At 390 × 844, the fixed 720-pixel transcript is placed before the interaction form, requiring substantial scrolling before the learner can enter the next turn (`app.py`, approximately lines 618–647). The six clinical-workspace tabs also require horizontal scrolling.

Recommended change:

- Put the interaction form before the transcript on narrow screens.
- Reduce or dynamically size the transcript container.
- Consider a collapsible transcript or sticky interaction composer.
- Replace the six horizontally scrolling tabs with an accordion or selector on narrow screens.

### P1 — Announce new responses accessibly

The transcript is rendered as custom HTML without live-region semantics (`app.py`, approximately lines 310–330). A screen-reader user may not be told that a patient response or feedback has appeared after submission.

Recommended change:

- Give the transcript `role="log"` and `aria-live="polite"` semantics.
- Manage focus after submission so keyboard and screen-reader users can locate the new response and return to the composer.
- Test keyboard-only operation, focus order, 200% zoom and at least one common screen reader.

### P1 — Strengthen the learner-facing debrief

The reactions–analysis–summary structure is sound, but the usefulness of the evidence review currently depends heavily on automatic matching.

Recommended change:

- Show direct excerpts explaining what supported each judgement.
- Add concise **What went well**, **Consider next**, and **Try again** summaries.
- Offer a printable HTML or PDF report alongside the JSON export.
- Add an optional facilitator sign-off or discussion-notes field.

### P2 — Reduce repeated interface weight

The full prototype/safety banner appears across most pages. It is important, but consumes substantial space, particularly on mobile.

Recommended change:

- Keep the full statement in the prebrief and Safety & scope page.
- After acknowledgement, use a shorter persistent reminder with a link to the full explanation.
- Confirm this treatment with clinical-governance and information-governance reviewers before changing it.

### P2 — Maintainability and release reproducibility

`app.py` is a large single module, and the AI SDK dependencies are not version-bounded.

Recommended change:

- Gradually split learner simulation, debrief, facilitator tools, authoring and shared UI into separate modules.
- Add tested version ranges or a lock file for `google-genai` and `openai`.
- Preserve the deterministic engine and current separation between AI phrasing and authored clinical state.

### Suggested regression tests

1. A spoken pain assessment is recognised when both interaction fields are completed.
2. An unmatched turn is labelled unscored rather than receiving an arbitrary numerical score.
3. Relevant quoted learner evidence can appear even if no deterministic state transition is applied.
4. Learners cannot reveal facilitator-only state.
5. Changing setup cannot silently discard an active session.
6. Interaction inputs remain readily reachable at phone width.
7. A newly added transcript entry is exposed through an accessible live region.

### Existing strengths to preserve

- Deterministic educator-authored clinical and consent state.
- Clear synthetic-data and non-clinical-guidance boundaries.
- Coached and immersive practice modes.
- Scenario-specific prebriefs and structured debriefing.
- Learner-safe export and separation of facilitator-only notes.
- Authored fallbacks when an AI provider is unavailable.
- Strong unit coverage for the simulation engine, AI safety boundaries, scenario validation and publishing.
