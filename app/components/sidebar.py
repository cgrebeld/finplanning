"""Sidebar component: file path, scenario, year range, action buttons."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

try:
    from streamlit_ace import st_ace
except ImportError:  # pragma: no cover - dependency is optional outside UI extras.
    st_ace = None

from finplanning_core.services.planning import PlanningService

from app.state import apply_yaml_edits, load_service, run_projection

EXAMPLES_DIR = Path("examples")
DEFAULT_PLAN_PATH = "examples/sample-plan.yaml"


def _list_example_plans() -> list[str]:
    """Return sorted paths of YAML plan files in examples/."""
    if not EXAMPLES_DIR.is_dir():
        return [DEFAULT_PLAN_PATH]
    plans = sorted(str(p) for p in EXAMPLES_DIR.glob("*.yaml") if p.name != "settings.yaml")
    return plans or [DEFAULT_PLAN_PATH]


def render_sidebar() -> None:
    """Render the sidebar with plan loading and projection controls."""
    with st.sidebar:
        st.header("Plan Configuration")

        options = _list_example_plans()
        current = st.session_state.get("plan_path") or DEFAULT_PLAN_PATH
        default_index = options.index(current) if current in options else 0
        plan_path = st.selectbox(
            "Plan file",
            options,
            index=default_index,
            key="plan_path_input",
            label_visibility="collapsed",
        )
        if st.button("Load", type="primary"):
            load_service(plan_path)

        service: PlanningService | None = st.session_state.get("service")
        if service is None:
            st.info("Load a plan to get started.")
            return

        scenario_ids = service.manager.scenario_ids
        selected_scenario = st.session_state.get("scenario_select")
        if selected_scenario not in scenario_ids:
            st.session_state["scenario_select"] = scenario_ids[0]
        col_scenario, col_start, col_end = st.columns([1.4, 1, 1], gap="small")
        with col_scenario:
            st.caption("Scenario")
            scenario_id = st.selectbox(
                "Scenario",
                scenario_ids,
                key="scenario_select",
                label_visibility="collapsed",
            )
            st.session_state["scenario_id"] = scenario_id
        with col_start:
            st.caption("Start")
            start_year = st.number_input(
                "Start year",
                min_value=2000,
                max_value=2100,
                step=1,
                key="start_year_input",
                label_visibility="collapsed",
            )
            st.session_state["start_year"] = int(start_year)
        with col_end:
            st.caption("End")
            end_year = st.number_input(
                "End year",
                min_value=2000,
                max_value=2200,
                step=1,
                key="end_year_input",
                label_visibility="collapsed",
            )
            st.session_state["end_year"] = int(end_year)

        with st.expander("Plan Data (YAML)", expanded=False):
            editor_version = st.session_state.get("editor_version", 0)
            if st_ace is not None:
                yaml_text = st_ace(
                    value=st.session_state.get("yaml_editor", ""),
                    language="yaml",
                    theme="tomorrow_night_bright",
                    key=f"yaml_editor_{editor_version}",
                    height=400,
                    auto_update=False,
                    tab_size=2,
                    wrap=True,
                    show_gutter=False,
                    show_print_margin=False,
                    font_size=14,
                )
                yaml_text = yaml_text or ""
            else:
                yaml_text = st.text_area(
                    "Edit plan YAML",
                    value=st.session_state.get("yaml_editor", ""),
                    height=400,
                    key=f"yaml_editor_{editor_version}",
                    label_visibility="collapsed",
                )
            if yaml_text != st.session_state.get("yaml_applied", ""):
                apply_yaml_edits(yaml_text)

        if st.button("Run Projection", type="primary"):
            run_projection()
