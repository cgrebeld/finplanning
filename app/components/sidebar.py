"""Sidebar component: file upload, sample selection, navigation, and projection controls."""

import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import streamlit as st
from finplanning_core.services import PlanningService

from app.state import MAX_YAML_SIZE_BYTES, load_service, load_service_from_yaml_text, run_projection

try:
    _APP_VERSION = version("finplanning-ui")
except PackageNotFoundError:  # pragma: no cover
    _APP_VERSION = "dev"

EXAMPLES_DIR = Path("examples")
DEFAULT_PLAN_PATH = "examples/sample-plan.yaml"

NAV_SECTIONS = [
    "Edit Plan",
    "Overview",
    "Net Worth",
    "Cash Flow",
    "Tax Analysis",
    "Monte Carlo",
    "Data & Export",
]

_NAV_ICONS = {
    "Edit Plan":    "✏️",
    "Overview":     "⚖️",
    "Cash Flow":    "🔀",
    "Net Worth":    "📈",
    "Tax Analysis": "🔥",
    "Monte Carlo":  "🎲",
    "Data & Export":"📥",
}


def _list_example_plans() -> list[str]:
    """Return sorted paths of YAML plan files in examples/."""
    if not EXAMPLES_DIR.is_dir():
        return [DEFAULT_PLAN_PATH]
    plans = sorted(str(p) for p in EXAMPLES_DIR.glob("*.yaml") if p.name != "settings.yaml")
    return plans or [DEFAULT_PLAN_PATH]


@st.dialog("Load Plan from File")
def _load_file_dialog() -> None:
    """Modal dialog for uploading a local YAML plan file."""
    uploaded = st.file_uploader(
        "Choose a YAML plan file",
        type=["yaml", "yml"],
        label_visibility="collapsed",
    )
    if uploaded is None:
        st.caption("Accepts .yaml or .yml files — max 100 KB.")
        return

    # Size guard (client-side byte count).
    if uploaded.size > MAX_YAML_SIZE_BYTES:
        st.error(f"File too large — maximum {MAX_YAML_SIZE_BYTES // 1024} KB.")
        return

    # Immediate parse validation — surfaces errors before the user clicks Load.
    content = uploaded.read().decode("utf-8")
    parse_error: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            PlanningService.from_yaml(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        parse_error = str(exc)

    if parse_error:
        st.error(parse_error)
        return

    if st.button("Load Plan", type="primary"):
        load_service_from_yaml_text(content)
        st.session_state["nav_section"] = "Edit Plan"
        st.rerun()


@st.dialog("Load Sample Plan")
def _load_sample_dialog() -> None:
    """Modal dialog for selecting a bundled example plan."""
    options = _list_example_plans()
    selected = st.radio(
        "Choose a sample plan",
        options,
        label_visibility="collapsed",
    )
    if st.button("Load Selected", type="primary"):
        load_service(selected)
        st.session_state["nav_section"] = "Edit Plan"
        st.rerun()


def render_sidebar() -> None:
    """Render the sidebar with plan loading, navigation, and projection controls."""
    with st.sidebar:
        st.header("Plan Configuration")

        col_load, col_sample = st.columns(2)
        with col_load:
            if st.button("Load", use_container_width=True):
                _load_file_dialog()
        with col_sample:
            if st.button("Load Sample", use_container_width=True):
                _load_sample_dialog()

        service: PlanningService | None = st.session_state.get("service")
        if service is None:
            st.info("Load a plan or sample to get started.")
            return

        st.divider()

        st.radio(
            "Navigate",
            options=NAV_SECTIONS,
            key="nav_section",
            label_visibility="collapsed",
            format_func=lambda s: f"{_NAV_ICONS.get(s, '')} {s}",
        )

        st.divider()

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

        st.divider()
        if st.button("Run Projection", type="primary", use_container_width=True):
            run_projection()
            st.rerun()

        st.markdown(
            f'<div class="app-version">v{_APP_VERSION}</div>',
            unsafe_allow_html=True,
        )
