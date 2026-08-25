"""Nurse Simulation Studio — deterministic first prototype."""

from __future__ import annotations

from copy import deepcopy
from html import escape
import json

import streamlit as st

from modules import ai_client
from modules.patient_dialogue import (
    ACTION_MAPPING_CONFIDENCE,
    ASSESSMENT_CRITERIA,
    assess_proposed_action,
    authored_dialogue_fallback,
    generate_interaction_evaluation,
)
from modules.simulation_engine import (
    add_learner_action,
    apply_action,
    append_patient_response,
    case_by_id,
    end_session,
    load_cases,
    new_session,
    record_learner_dialogue,
    record_nursing_note,
    record_unmapped_action,
    remove_latest_patient_response,
    start_session,
    student_export,
)


st.set_page_config(
    page_title="Nurse Simulation Studio",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data
def get_cases():
    return load_cases()


CASES = get_cases()


def apply_styles() -> None:
    st.markdown(
        """
        <style>
          :root { --ink:#172321; --muted:#5d6c68; --teal:#0f766e; --line:#d7e2df; }
          .block-container { max-width: 1220px; padding-top: 2rem; padding-bottom: 4rem; }
          [data-testid="stSidebar"] { border-right: 1px solid var(--line); }
          .hero { padding: 2.2rem; border-radius: 22px; color: white;
            background: linear-gradient(125deg,#0a4f4a 0%,#0f766e 58%,#34988e 100%);
            box-shadow: 0 16px 35px rgba(15,118,110,.16); margin-bottom: 1.4rem; }
          .hero small { letter-spacing:.12em; text-transform:uppercase; opacity:.8; font-weight:700; }
          .hero h1 { color:white; font-size:2.65rem; margin:.35rem 0 .5rem; }
          .hero p { max-width:720px; font-size:1.08rem; margin:0; opacity:.92; }
          .safety-banner { border-left:5px solid #d97706; background:#fff8e8;
            padding:.85rem 1rem; border-radius:8px; margin:.8rem 0 1.4rem; color:#5d3b08; }
          .patient-header { padding:1.2rem 1.4rem; background:white; border:1px solid var(--line);
            border-radius:16px; margin-bottom:1rem; }
          .patient-header h2 { margin:0 0 .35rem; }
          .muted { color:var(--muted); }
          .transcript { border-left:3px solid var(--line); padding:.2rem 0 .2rem 1rem; margin:.65rem 0; }
          .transcript.patient { border-left-color:#0f766e; }
          .transcript.learner { border-left-color:#3157d5; }
          .transcript.cue { border-left-color:#d97706; background:#fffaf0; padding:.65rem 1rem; border-radius:0 8px 8px 0; }
          .transcript.nonverbal { border-left-color:#8b5cf6; color:#51416f; font-style:italic; }
          .transcript.documentation { border-left-color:#64748b; background:#f8fafc; padding:.65rem 1rem; border-radius:0 8px 8px 0; }
          .mode-card { border:1px solid var(--line); border-radius:14px; padding:1rem; background:#f8fbfa; margin:.5rem 0 1rem; }
          .minute { color:var(--muted); font-size:.78rem; font-weight:600; text-transform:uppercase; }
          div[data-testid="stMetric"] { background:white; border:1px solid var(--line); padding:1rem; border-radius:14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def safety_banner() -> None:
    st.markdown(
        """
        <div class="safety-banner"><strong>Prototype:</strong> entirely fictional cases and
        deterministic clinical state. AI may interpret an interaction and phrase the patient's
        response, but cannot change clinical facts. This app is not clinical guidance, a medicines
        reference or a competence-assessment system.</div>
        """,
        unsafe_allow_html=True,
    )


def case_selector(key: str = "case_select") -> dict:
    selected = st.selectbox(
        "Select a synthetic patient",
        [case["case_id"] for case in CASES],
        format_func=lambda value: (
            f"{case_by_id(CASES, value)['patient']['display_name']} — "
            f"{case_by_id(CASES, value)['title']}"
        ),
        key=key,
    )
    return case_by_id(CASES, selected)


def render_home() -> None:
    st.markdown(
        """
        <section class="hero">
          <small>Supervised deliberate practice</small>
          <h1>Nurse Simulation Studio</h1>
          <p>Rehearse person-centred communication, observation and escalation with
          synthetic patients. Clinical state changes are authored and deterministic.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    safety_banner()

    cols = st.columns(3)
    cols[0].metric("Synthetic patients", len(CASES))
    cols[1].metric("Clinical field", "Adult nursing")
    cols[2].metric("AI-generated physiology", "None")

    st.subheader("A simple practice loop")
    loop_cols = st.columns(3)
    for column, number, title, text in zip(
        loop_cols,
        ("01", "02", "03"),
        ("Choose", "Rehearse", "Debrief"),
        (
            "Select one focused patient case and review the learner brief.",
            "Describe what you would do and say, then notice the patient's words and behaviour.",
            "Review the encounter using a structured, facilitator-supported debrief.",
        ),
    ):
        with column:
            with st.container(border=True):
                st.caption(number)
                st.markdown(f"### {title}")
                st.write(text)

    st.subheader("Included practice cases")
    for case in CASES:
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.markdown(f"#### {case['patient']['display_name']} · {case['title']}")
                st.write(case["clinical"]["presenting_context"])
                st.caption(f"{case['setting'].title()} · {case['complexity'].title()}")
            with right:
                st.metric("Suggested time", f"{case['estimated_duration_minutes']} min")


def render_library() -> None:
    st.title("Synthetic patient library")
    safety_banner()
    case = case_selector("library_case")
    patient = case["patient"]
    st.markdown(
        f"""
        <div class="patient-header">
          <h2>{patient['display_name']}</h2>
          <div class="muted">Age {patient['age']} · {patient['pronouns']} ·
          {case['setting'].title()} · {case['complexity'].title()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        st.subheader("Learner context")
        st.write(case["clinical"]["presenting_context"])
        st.markdown("**Visible at the start**")
        for cue in case["clinical"]["visible_at_start"]:
            st.markdown(f"- {cue}")
        st.markdown("**Communication needs**")
        for need in patient["communication_needs"]:
            st.markdown(f"- {need}")
    with right:
        st.subheader("Learning outcomes")
        for outcome in case["learning"]["outcomes"]:
            st.markdown(f"- {outcome}")
        st.markdown("**NMC proficiency platforms represented**")
        for platform in case["learning"]["nmc_platforms"]:
            st.markdown(f"- {platform}")


def ensure_session(case: dict, learner_name: str, practice_mode: str) -> dict:
    session = st.session_state.get("simulation")
    if (
        session is None
        or session.get("case_id") != case["case_id"]
        or session.get("practice_mode", "coached") != practice_mode
    ):
        session = new_session(
            case,
            learner_name,
            practice_mode=practice_mode,
            start_in_prebrief=True,
        )
        st.session_state.simulation = session
    return session


def render_prebrief(case: dict, session: dict) -> None:
    prebrief = case["prebrief"]
    mode_name = "Coached practice" if session["practice_mode"] == "coached" else "Immersive practice"
    st.markdown(f"### Prebrief · {mode_name}")
    st.markdown(f'<div class="mode-card"><strong>Your role</strong><br>{escape(prebrief["role"])}</div>', unsafe_allow_html=True)
    st.write(prebrief["orientation"])
    left, middle, right = st.columns(3)
    with left:
        st.markdown("**Available resources**")
        for item in prebrief["resources"]:
            st.markdown(f"- {item}")
    with middle:
        st.markdown("**Fidelity limits**")
        for item in prebrief["limitations"]:
            st.markdown(f"- {item}")
    with right:
        st.markdown("**Learning agreement**")
        for item in prebrief["ground_rules"]:
            st.markdown(f"- {item}")
    st.info(
        "In immersive practice, interaction scores remain hidden until the simulation ends. "
        "The patient response and visible scenario changes remain available."
        if session["practice_mode"] == "immersive"
        else "In coached practice, formative feedback appears after each interaction."
    )
    if st.button("I am ready — begin simulation", type="primary", use_container_width=True):
        start_session(session)
        st.rerun()


def render_transcript(session: dict) -> None:
    st.subheader("Interaction")
    for item in session["transcript"]:
        css_role = "patient"
        if item["role"].startswith("learner"):
            css_role = "learner"
        elif item["role"] == "cue":
            css_role = "cue"
        elif item["role"] in {"nonverbal", "documentation"}:
            css_role = item["role"]
        latency = str(item.get("response_latency", "")).replace("_", " ")
        latency_label = f" · {escape(latency)}" if latency and latency != "immediate" else ""
        st.markdown(
            f"""
            <div class="transcript {css_role}">
              <div class="minute">Minute {item['minute']} · {escape(str(item['speaker']))}{latency_label}</div>
              <div>{escape(str(item['text']))}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_state(case: dict, session: dict, facilitator_mode: bool) -> None:
    state = session["state"]
    patient = case["patient"]
    st.markdown(
        f"""
        <div class="patient-header">
          <h2>{patient['display_name']}</h2>
          <div class="muted">Age {patient['age']} · {patient['pronouns']} ·
          prefers “{patient['preferred_address']}” · {case['setting'].title()}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    metric_cols = st.columns(3)
    metric_cols[0].metric("Scenario time", f"{state['elapsed_minutes']} min")
    metric_cols[1].metric("Actions recorded", len(session["action_log"]))
    metric_cols[2].metric("Mode", session.get("practice_mode", "coached").title())

    patient_tab, handover_tab, observations_tab, records_tab, environment_tab, notes_tab = st.tabs(
        ["Patient", "Handover", "Observations", "Records", "Environment", "Notes"]
    )
    with patient_tab:
        st.write(case["clinical"]["presenting_context"])
        st.markdown("**Communication needs**")
        for need in patient["communication_needs"]:
            st.markdown(f"- {need}")
        st.markdown("**What you can see now**")
        cues = [
            *case["clinical"]["visible_at_start"],
            *state.get("revealed_cues", []),
        ]
        for cue in cues:
            st.markdown(f"- {cue}")

    with handover_tab:
        st.write(case["clinical_workspace"]["handover"])

    with observations_tab:
        if state.get("observations_measured"):
            st.json(case["clinical"]["baseline_observations"])
        elif case["clinical"].get("baseline_observations"):
            st.info(
                "No observation set has been revealed in this encounter. Describe what you would do in the action box."
            )
        else:
            st.caption("No observation chart is needed for this focused conversation scenario.")

    with records_tab:
        records = case["clinical_workspace"].get("record_access", [])
        if not records:
            st.caption("No additional record is required for this focused scenario.")
        for record in records:
            if state.get(record["state_key"]):
                st.markdown(f"**{record['title']}**")
                st.write(record["content"])
            else:
                st.markdown(f"**{record['title']}**")
                st.caption("Not yet accessed in the encounter.")

    with environment_tab:
        st.markdown("**Current environment**")
        for item in case["clinical_workspace"]["environment"]:
            st.markdown(f"- {item}")
        st.markdown("**Resources represented in this simulation**")
        for item in case["clinical_workspace"]["available_resources"]:
            st.markdown(f"- {item}")

    with notes_tab:
        for note in session.get("nursing_notes", []):
            st.caption(f"Minute {note['minute']} · {note['author']}")
            st.write(note["text"])
        with st.form(f"nursing_note_{case['case_id']}", clear_on_submit=True):
            note_text = st.text_area(
                "Add a nursing note",
                placeholder="Document what is relevant, concise and factual…",
                disabled=session["status"] == "ended",
            )
            save_note = st.form_submit_button(
                "Save note",
                disabled=session["status"] == "ended",
                use_container_width=True,
            )
        if save_note:
            result = record_nursing_note(case, session, note_text)
            if result.applied:
                st.rerun()
            else:
                st.warning(result.message)

    if facilitator_mode:
        with st.expander("Facilitator-only state", expanded=False):
            st.json(state)
            st.markdown("**Expected safety points**")
            for item in case["facilitator_only"]["expected_safety_points"]:
                st.markdown(f"- {item}")


def render_latest_feedback(session: dict) -> None:
    feedback_log = session.get("feedback_log", [])
    if not feedback_log:
        return
    latest = feedback_log[-1]
    rating = latest["rating"]
    labels = {
        "appropriate": "Appropriate for this patient state",
        "concerning": "Concerning for this patient state",
        "unclear": "Unclear — facilitator review needed",
    }
    st.markdown("#### Formative interaction feedback")
    score = latest.get("suitability_score")
    if score is not None:
        score_labels = {
            1: "Clearly concerning",
            2: "Concerning",
            3: "Mixed or unclear",
            4: "Appropriate",
            5: "Strongly appropriate",
        }
        st.markdown(f"**Proposed action suitability: {score}/5 — {score_labels[score]}**")
    relevance = latest.get("relevance_category")
    if relevance:
        st.caption(f"Relevance to this moment: {relevance.replace('_', ' ').title()}")
    if rating == "appropriate":
        st.success(f"**Combined interaction: {labels[rating]}**  \n{latest['feedback']}")
    elif rating == "concerning":
        st.warning(f"**Combined interaction: {labels[rating]}**  \n{latest['feedback']}")
    else:
        st.info(f"**Combined interaction: {labels[rating]}**  \n{latest['feedback']}")
    source = (
        "AI-supported"
        if latest.get("generated") or latest.get("action_assessment_generated")
        else "Authored fallback"
    )
    st.caption(f"{source} feedback on this interaction only · not a competence assessment")
    with st.expander("How action suitability is judged", expanded=False):
        for criterion in ASSESSMENT_CRITERIA:
            st.markdown(f"- {criterion}")
        st.markdown("**Case-specific educator criteria**")
        for criterion in session.get("educator_rubric", []):
            st.markdown(f"- **{criterion['label']}:** {criterion['guidance']}")


def render_feedback_history(session: dict) -> None:
    feedback_log = session.get("feedback_log", [])
    if not feedback_log:
        st.info("No formative interaction feedback was recorded in this encounter.")
        return
    for index, item in enumerate(feedback_log, start=1):
        with st.expander(
            f"Interaction {index} · minute {item.get('minute', 0)} · "
            f"{item.get('rating', 'unclear').title()}",
            expanded=index == len(feedback_log),
        ):
            if item.get("action"):
                st.markdown(f"**Action:** {item['action']}")
            if item.get("dialogue"):
                st.markdown(f"**Words:** {item['dialogue']}")
            score = item.get("suitability_score")
            relevance = item.get("relevance_category")
            if score is not None:
                st.write(
                    f"Suitability {score}/5"
                    + (f" · {relevance.replace('_', ' ').title()} relevance" if relevance else "")
                )
            st.write(item.get("feedback", "No feedback text was recorded."))


def render_simulation(facilitator_mode: bool) -> None:
    st.title("Run simulation")
    safety_banner()
    setup_left, setup_middle, setup_right = st.columns([2, 1.25, 1])
    with setup_left:
        case = case_selector("simulation_case")
    with setup_middle:
        practice_mode_label = st.radio(
            "Practice style",
            ["Coached", "Immersive"],
            horizontal=True,
            help="Coached shows feedback after each turn; Immersive holds it for debrief.",
        )
    with setup_right:
        learner_name = st.text_input("Learner name", value="Learner")

    practice_mode = practice_mode_label.casefold()
    session = ensure_session(case, learner_name, practice_mode)

    if session.get("phase") == "prebrief":
        render_prebrief(case, session)
        return

    reset_col, end_col, _ = st.columns([1, 1, 3])
    if reset_col.button("Restart case", use_container_width=True):
        st.session_state.simulation = new_session(
            case,
            learner_name,
            practice_mode=practice_mode,
            start_in_prebrief=True,
        )
        st.rerun()
    if end_col.button(
        "End simulation",
        type="primary",
        use_container_width=True,
        disabled=session["status"] == "ended",
    ):
        end_session(session)
        st.rerun()

    left, right = st.columns([1.25, 1])
    with left:
        render_state(case, session, facilitator_mode)
    with right:
        st.subheader("Plan your interaction")
        st.caption(
            "The proposed action and spoken words are considered together against the "
            "patient's current authored state."
        )
        with st.form("interaction_form", clear_on_submit=True):
            action_text = st.text_area(
                "What are you going to do?",
                height=95,
                placeholder="Describe one clear nursing action…",
                disabled=session["status"] == "ended",
            )
            dialogue = st.text_area(
                "What would you say?",
                height=95,
                placeholder="Write the words you would use with the patient…",
                disabled=session["status"] == "ended",
            )
            submitted = st.form_submit_button(
                "Submit interaction",
                type="primary",
                use_container_width=True,
                disabled=session["status"] == "ended",
            )
        if submitted:
            action_clean = " ".join(action_text.split())[:600]
            dialogue_clean = " ".join(dialogue.split())[:600]
            if not action_clean and not dialogue_clean:
                st.warning("Describe an action, enter something to say, or provide both.")
            else:
                state_before = deepcopy(session["state"])
                canonical_reply = authored_dialogue_fallback(case, session)
                action_status = "not_provided"
                matched_action_label = None
                action_assessment = None
                latest_action = None

                if action_clean:
                    if AI_READY:
                        with st.spinner("Assessing the proposed action against the patient state…"):
                            action_assessment = assess_proposed_action(
                                case, session, action_clean, dialogue_clean
                            )

                    can_apply_ai_mapping = bool(
                        action_assessment
                        and action_assessment.generated
                        and action_assessment.matched_action_id
                        and action_assessment.confidence >= ACTION_MAPPING_CONFIDENCE
                        and action_assessment.suitability_score >= 4
                    )
                    if can_apply_ai_mapping:
                        action_result = apply_action(
                            case,
                            session,
                            action_assessment.matched_action_id,
                            learner_text=action_clean,
                        )
                    elif AI_READY:
                        action_result = record_unmapped_action(
                            case, session, action_clean
                        )
                    else:
                        action_result = add_learner_action(case, session, action_clean)

                    if not action_result.applied:
                        action_status = "blocked"
                        canonical_reply = action_result.message
                    else:
                        latest_action = session["action_log"][-1]
                        if latest_action.get("applied"):
                            action_status = "applied"
                            matched_action_label = latest_action["label"]
                            canonical_reply = action_result.message
                            remove_latest_patient_response(session)
                        else:
                            action_status = (
                                "assessed_only" if action_assessment else "unrecognised"
                            )

                if dialogue_clean:
                    dialogue_minutes = 0 if action_status in {"applied", "unrecognised"} else 1
                    record_learner_dialogue(
                        case, session, dialogue_clean, minutes=dialogue_minutes
                    )

                def evaluate():
                    return generate_interaction_evaluation(
                        case=case,
                        session=session,
                        state_before=state_before,
                        action_text=action_clean,
                        dialogue_text=dialogue_clean,
                        action_status=action_status,
                        canonical_reply=canonical_reply,
                        matched_action_label=matched_action_label,
                        action_assessment=action_assessment,
                    )

                if AI_READY:
                    with st.spinner("The patient is responding and the interaction is being reviewed…"):
                        evaluation = evaluate()
                else:
                    evaluation = evaluate()

                append_patient_response(
                    case,
                    session,
                    evaluation.patient_reply,
                    nonverbal_cue=evaluation.nonverbal_cue,
                    response_latency=evaluation.response_latency,
                )
                fallback_score = {
                    "applied": 4,
                    "blocked": 2,
                    "unrecognised": 3,
                    "assessed_only": 3,
                }.get(action_status)
                session.setdefault("feedback_log", []).append(
                    {
                        "minute": session["state"]["elapsed_minutes"],
                        "action": action_clean,
                        "dialogue": dialogue_clean,
                        "action_status": action_status,
                        "suitability_score": (
                            action_assessment.suitability_score
                            if action_assessment
                            else fallback_score
                        ),
                        "suitability_band": (
                            action_assessment.suitability_band
                            if action_assessment
                            else None
                        ),
                        "relevance_category": (
                            action_assessment.relevance_category
                            if action_assessment
                            else "direct"
                            if action_status == "applied"
                            else "unclear"
                        ),
                        "mapping_confidence": (
                            action_assessment.confidence if action_assessment else None
                        ),
                        "matched_action_id": (
                            action_assessment.matched_action_id
                            if action_assessment
                            else latest_action.get("action_id")
                            if latest_action
                            else None
                        ),
                        "rating": evaluation.rating,
                        "feedback": evaluation.feedback,
                        "generated": evaluation.generated,
                        "action_assessment_generated": (
                            action_assessment.generated if action_assessment else False
                        ),
                        "patient_nonverbal_cue": evaluation.nonverbal_cue,
                        "response_latency": evaluation.response_latency,
                    }
                )
                st.rerun()

        if session.get("practice_mode") == "coached":
            render_latest_feedback(session)
        elif session.get("feedback_log"):
            st.caption(
                "Immersive practice is active: interaction scores and coaching are being held for debrief."
            )

    st.divider()
    render_transcript(session)
    if session["status"] == "ended":
        st.success("Simulation ended. Open Debrief from the navigation to reflect and export.")


def render_educator_rubric(session: dict) -> None:
    st.markdown("### Editable educator criteria")
    st.caption(
        "These criteria guide AI-supported interaction feedback and facilitator discussion. "
        "They do not produce an automatic competence decision."
    )
    rubric = session.setdefault("educator_rubric", [])
    for index, criterion in enumerate(rubric):
        with st.expander(criterion["label"], expanded=False):
            criterion["label"] = st.text_input(
                "Criterion label",
                value=criterion["label"],
                key=f"rubric_label_{session['case_id']}_{index}",
            )
            criterion["guidance"] = st.text_area(
                "Case-specific guidance",
                value=criterion["guidance"],
                key=f"rubric_guidance_{session['case_id']}_{index}",
            )
            criterion["facilitator_rating"] = st.selectbox(
                "Facilitator observation",
                ["Not assessed", "Observed", "Partly observed", "Not yet observed"],
                index=["Not assessed", "Observed", "Partly observed", "Not yet observed"].index(
                    criterion.get("facilitator_rating", "Not assessed")
                ),
                key=f"rubric_rating_{session['case_id']}_{index}",
            )
            criterion["facilitator_note"] = st.text_area(
                "Facilitator evidence note",
                value=criterion.get("facilitator_note", ""),
                key=f"rubric_note_{session['case_id']}_{index}",
            )


def render_debrief(facilitator_mode: bool) -> None:
    st.title("Structured debrief")
    safety_banner()
    session = st.session_state.get("simulation")
    if not session:
        st.info("Run a simulation first. The debrief will use that session's transcript.")
        return
    case = case_by_id(CASES, session["case_id"])
    if session["status"] == "active":
        st.warning("The simulation is still active. End it when you are ready to debrief.")

    st.subheader(f"{case['patient']['display_name']} · {case['title']}")
    cols = st.columns(3)
    cols[0].metric("Elapsed", f"{session['state']['elapsed_minutes']} min")
    cols[1].metric("Actions", len(session["action_log"]))
    cols[2].metric("Visible changes", len(session["state"].get("revealed_cues", [])))

    if session["status"] == "ended":
        st.markdown("### Formative interaction review")
        render_feedback_history(session)
    elif session.get("practice_mode") == "immersive":
        st.info("Immersive-mode feedback remains hidden until the simulation is ended.")

    st.markdown("### Reactions")
    reaction_prompt = "How did the encounter feel, and what moment stays with you?"
    reaction_key = f"reflection_{case['case_id']}_reaction"
    reaction = st.text_area(
        reaction_prompt,
        value=session.get("reflection", {}).get(reaction_prompt, ""),
        key=reaction_key,
    )
    session.setdefault("reflection", {})[reaction_prompt] = reaction

    st.markdown("### Analysis")
    for index, prompt in enumerate(case["debrief"]["prompts"]):
        key = f"reflection_{case['case_id']}_{index}"
        saved = session.get("reflection", {}).get(prompt, "")
        answer = st.text_area(prompt, value=saved, key=key)
        session.setdefault("reflection", {})[prompt] = answer

    st.markdown("### Summary and transfer")
    transfer_prompt = "What is one specific thing you would carry into supervised practice?"
    transfer_key = f"reflection_{case['case_id']}_transfer"
    transfer = st.text_area(
        transfer_prompt,
        value=session.get("reflection", {}).get(transfer_prompt, ""),
        key=transfer_key,
    )
    session.setdefault("reflection", {})[transfer_prompt] = transfer

    if facilitator_mode:
        render_educator_rubric(session)

    with st.expander("Review transcript", expanded=False):
        render_transcript(session)

    export = student_export(case, session)
    st.download_button(
        "Download learner-safe session JSON",
        data=json.dumps(export, indent=2, ensure_ascii=False),
        file_name=f"{case['case_id'].lower()}_simulation_session.json",
        mime="application/json",
    )
    st.caption(
        "The export excludes facilitator-only notes and does not make an automatic competence decision."
    )


def render_about() -> None:
    st.title("Safety and scope")
    safety_banner()
    st.markdown(
        """
        ### What this version does

        - Uses four entirely fictional adult-nursing cases.
        - Applies clinical and consent changes through authored rules.
        - Offers coached practice or immersive practice with delayed debrief feedback.
        - Includes prebriefing, a small clinical workspace and learner documentation.
        - Optionally uses constrained AI for natural dialogue and formative interpretation.
        - Falls back to authored dialogue if an API is unavailable.
        - Uses bounded patient-experience state, non-verbal cues and visible time changes.
        - Supports replay, structured debrief, editable educator criteria and learner-safe export.

        ### What it does not do

        - Provide clinical guidance or medicine doses.
        - Calculate a clinical score or recommend treatment.
        - Replace supervision, assessment or real practice learning.
        - Determine learner competence.
        - Allow AI dialogue to change observations, consent or treatment effects.

        ### Before educational deployment

        Cases need local approval by nursing educators and relevant clinical,
        simulation, medicines, accessibility and information-governance leads.
        Local escalation processes and educator-authored clinical content must replace
        generic placeholders.
        """
    )


apply_styles()
with st.sidebar:
    st.markdown("## 🩺 Nurse Simulation Studio")
    st.caption("Deterministic prototype · v0.1")
    page = st.radio(
        "Navigation",
        ["Home", "Patient library", "Run simulation", "Debrief", "Safety & scope"],
        label_visibility="collapsed",
    )
    FACILITATOR_MODE = st.toggle(
        "Facilitator mode",
        value=False,
        help="Shows internal authored state and editable case-specific educator criteria.",
    )
    st.divider()
    with st.expander("AI interaction settings", expanded=False):
        ai_client.render_provider_options()
        AI_READY, ai_status = ai_client.configure_selected_provider()
        st.caption(ai_status if AI_READY else f"Authored fallback active. {ai_status}")
    st.divider()
    st.caption("Entirely fictional training data. No real patient records.")

if page == "Home":
    render_home()
elif page == "Patient library":
    render_library()
elif page == "Run simulation":
    render_simulation(FACILITATOR_MODE)
elif page == "Debrief":
    render_debrief(FACILITATOR_MODE)
else:
    render_about()
