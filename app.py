"""Nurse Simulation Studio — deterministic first prototype."""

from __future__ import annotations

from html import escape
import json

import streamlit as st

from modules.simulation_engine import (
    add_learner_action,
    add_learner_dialogue,
    case_by_id,
    end_session,
    load_cases,
    new_session,
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
        authored responses. This app is not clinical guidance, a medicines reference or a
        competence-assessment system.</div>
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
            "Use authored actions, speak to the patient and notice visible changes.",
            "End the scenario and reflect with a prepared facilitator.",
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


def ensure_session(case: dict, learner_name: str) -> dict:
    session = st.session_state.get("simulation")
    if session is None or session.get("case_id") != case["case_id"]:
        session = new_session(case, learner_name)
        st.session_state.simulation = session
    return session


def render_transcript(session: dict) -> None:
    st.subheader("Interaction")
    for item in session["transcript"]:
        css_role = "patient"
        if item["role"].startswith("learner"):
            css_role = "learner"
        elif item["role"] == "cue":
            css_role = "cue"
        st.markdown(
            f"""
            <div class="transcript {css_role}">
              <div class="minute">Minute {item['minute']} · {escape(str(item['speaker']))}</div>
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
    metric_cols[1].metric("Actions completed", len(session["action_log"]))
    metric_cols[2].metric("Status", session["status"].title())

    with st.expander("Patient brief and communication needs", expanded=False):
        st.write(case["clinical"]["presenting_context"])
        for need in patient["communication_needs"]:
            st.markdown(f"- {need}")

    with st.expander("Visible cues", expanded=True):
        cues = [*case["clinical"]["visible_at_start"], *state.get("revealed_cues", [])]
        for cue in cues:
            st.markdown(f"- {cue}")

    if state.get("observations_measured"):
        with st.expander("Measured observations", expanded=True):
            st.json(case["clinical"]["baseline_observations"])

    if facilitator_mode:
        with st.expander("Facilitator-only state", expanded=False):
            st.json(state)
            st.markdown("**Expected safety points**")
            for item in case["facilitator_only"]["expected_safety_points"]:
                st.markdown(f"- {item}")


def render_simulation() -> None:
    st.title("Run simulation")
    safety_banner()
    setup_left, setup_right = st.columns([2, 1])
    with setup_left:
        case = case_selector("simulation_case")
    with setup_right:
        learner_name = st.text_input("Learner name", value="Learner")

    facilitator_mode = st.sidebar.toggle(
        "Facilitator mode",
        value=False,
        help="Shows authored facilitator notes and internal deterministic state.",
    )
    session = ensure_session(case, learner_name)

    reset_col, end_col, _ = st.columns([1, 1, 3])
    if reset_col.button("Restart case", use_container_width=True):
        st.session_state.simulation = new_session(case, learner_name)
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
        st.subheader("Take a nursing action")
        st.caption(
            "Describe one action you intend to take. The available actions are not shown."
        )
        with st.form("action_form", clear_on_submit=True):
            action_text = st.text_area(
                "What are you going to do?",
                height=95,
                placeholder="Describe one clear nursing action…",
                disabled=session["status"] == "ended",
            )
            action_submitted = st.form_submit_button(
                "Take action · advances 2 minutes",
                type="primary",
                use_container_width=True,
                disabled=session["status"] == "ended",
            )
        if action_submitted:
            result = add_learner_action(case, session, action_text)
            if result.applied:
                st.rerun()
            else:
                st.warning(result.message)

        st.divider()
        st.subheader("Speak to the patient")
        st.caption(
            "Free text receives an authored neutral reply and cannot change clinical facts."
        )
        with st.form("dialogue_form", clear_on_submit=True):
            dialogue = st.text_area(
                "What would you say?",
                height=95,
                disabled=session["status"] == "ended",
            )
            submitted = st.form_submit_button(
                "Send · advances 1 minute",
                use_container_width=True,
                disabled=session["status"] == "ended",
            )
        if submitted:
            result = add_learner_dialogue(case, session, dialogue)
            if result.applied:
                st.rerun()
            else:
                st.warning(result.message)

    st.divider()
    render_transcript(session)
    if session["status"] == "ended":
        st.success("Simulation ended. Open Debrief from the navigation to reflect and export.")


def render_debrief() -> None:
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

    st.markdown("### Learner reflection")
    for index, prompt in enumerate(case["debrief"]["prompts"]):
        key = f"reflection_{case['case_id']}_{index}"
        saved = session.get("reflection", {}).get(prompt, "")
        answer = st.text_area(prompt, value=saved, key=key)
        session.setdefault("reflection", {})[prompt] = answer

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
        - Uses authored dialogue rather than generative AI.
        - Supports replay, visible time changes, debrief and learner-safe export.

        ### What it does not do

        - Provide clinical guidance or medicine doses.
        - Calculate a clinical score or recommend treatment.
        - Replace supervision, assessment or real practice learning.
        - Determine learner competence.

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
    st.divider()
    st.caption("Entirely fictional training data. No real patient records.")

if page == "Home":
    render_home()
elif page == "Patient library":
    render_library()
elif page == "Run simulation":
    render_simulation()
elif page == "Debrief":
    render_debrief()
else:
    render_about()
