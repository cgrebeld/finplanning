"""Session state helpers for the Streamlit UI."""

from __future__ import annotations

import contextlib
import tempfile
from datetime import date
from pathlib import Path
from typing import Literal

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.risk.monte_carlo import MonteCarloConfig
from finplanning_core.services.planning import PlanningService
from streamlit.errors import StreamlitAPIException

MAX_MC_ITERATIONS = 2000
MAX_YAML_SIZE_BYTES = 100 * 1024
MonteCarloReturnMethod = Literal["historical", "parametric"]
MC_RETURN_METHODS: tuple[MonteCarloReturnMethod, ...] = ("historical", "parametric")

_DEFAULTS: dict[str, object] = {
    "service": None,
    "projection": None,
    "scenario_id": None,
    "scenario_select": None,
    "start_year": None,
    "start_year_input": None,
    "end_year": None,
    "end_year_input": None,
    "plan_path": "",
    "error": None,
    "mc_result": None,
    "mc_running": False,
    "yaml_text": "",
    "yaml_applied": "",
    "yaml_editor": "",
    "yaml_edit_error": None,
    "selected_flow_year": None,
    "nav_section": "Edit Plan",
}


def init_state() -> None:
    """Ensure all session-state keys exist (idempotent)."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def _set_scenario_and_year_controls(service: PlanningService) -> None:
    """Reset scenario/year controls so widgets and canonical fields stay aligned.

    Widget keys (``scenario_select``, ``start_year_input``, ``end_year_input``)
    cannot be written after Streamlit has already instantiated those widgets in
    the current script run.  We guard each write so that late callers (e.g.
    ``apply_yaml_edits``, invoked from the YAML editor *below* the widgets)
    only update the canonical keys; the widget keys will catch up on the next
    rerun triggered by ``st.rerun()`` or user interaction.
    """
    plan = service.plan
    base_scenario_id = plan.base_scenario_id

    today_year = date.today().year
    max_age = max(p.life_expectancy_age for p in plan.persons)
    youngest_birth = max(p.birth_date.year for p in plan.persons)
    end_year = youngest_birth + max_age

    st.session_state["scenario_id"] = base_scenario_id
    st.session_state["start_year"] = today_year
    st.session_state["end_year"] = end_year
    st.session_state["selected_flow_year"] = None

    # Only touch widget keys when Streamlit hasn't rendered them yet.
    for widget_key, value in [
        ("scenario_select", base_scenario_id),
        ("start_year_input", today_year),
        ("end_year_input", end_year),
    ]:
        with contextlib.suppress(StreamlitAPIException):
            st.session_state[widget_key] = value


def _sync_selected_flow_year(projection: ProjectionResult) -> None:
    """Ensure selected_flow_year always points to a valid projection year."""
    if not projection.years:
        st.session_state["selected_flow_year"] = None
        return

    valid_years = {year.year for year in projection.years}
    selected = st.session_state.get("selected_flow_year")
    if not isinstance(selected, int) or selected not in valid_years:
        st.session_state["selected_flow_year"] = projection.years[0].year


def set_selected_flow_year(year: int) -> None:
    """Persist a selected Net Worth/Sankey year in session state."""
    st.session_state["selected_flow_year"] = year


def get_selected_flow_year(projection: ProjectionResult) -> int:
    """Return the selected flow year, defaulting to the first projected year."""
    _sync_selected_flow_year(projection)
    selected = st.session_state.get("selected_flow_year")
    if not isinstance(selected, int):
        return projection.years[0].year
    return selected


def load_service(plan_path: str) -> None:
    """Load a PlanningService from a YAML path into session state."""
    try:
        service = PlanningService.from_yaml(plan_path)
        st.session_state["service"] = service
        st.session_state["projection"] = None
        st.session_state["mc_result"] = None
        st.session_state["mc_running"] = False
        st.session_state["error"] = None

        _set_scenario_and_year_controls(service)

        st.session_state["plan_path"] = plan_path

        yaml_content = Path(plan_path).read_text(encoding="utf-8")
        st.session_state["yaml_text"] = yaml_content
        st.session_state["yaml_applied"] = yaml_content
        st.session_state["yaml_editor"] = yaml_content
        st.session_state["editor_version"] = st.session_state.get("editor_version", 0) + 1
    except Exception as exc:  # noqa: BLE001
        st.session_state["error"] = str(exc)
        st.session_state["service"] = None
        st.session_state["projection"] = None
        st.session_state["mc_result"] = None
        st.session_state["mc_running"] = False


def run_projection() -> None:
    """Run the projection for the current scenario and year range."""
    service: PlanningService | None = st.session_state.get("service")
    if service is None:
        st.session_state["error"] = "No plan loaded. Please load a plan first."
        return

    try:
        result = service.run_projection(
            scenario_id=st.session_state.get("scenario_id"),
            start_year=st.session_state.get("start_year"),
            end_year=st.session_state.get("end_year"),
        )
        st.session_state["projection"] = result
        _sync_selected_flow_year(result)
        st.session_state["error"] = None
        if st.session_state.get("nav_section") == "Edit Plan":
            st.session_state["_nav_after_run"] = "Overview"
    except Exception as exc:  # noqa: BLE001
        st.session_state["error"] = str(exc)
        st.session_state["projection"] = None


def run_monte_carlo(
    n_iterations: int = 1000,
    seed: int | None = 42,
    return_method: MonteCarloReturnMethod = "historical",
    progress_bar: st.delta_generator.DeltaGenerator | None = None,
) -> None:
    """Run a Monte Carlo simulation and store the result in session state."""
    service: PlanningService | None = st.session_state.get("service")
    if service is None:
        st.session_state["error"] = "No plan loaded. Please load a plan first."
        return

    if st.session_state.get("mc_running"):
        st.session_state["error"] = "Monte Carlo simulation already running. Please wait for it to finish."
        return

    if n_iterations > MAX_MC_ITERATIONS:
        st.session_state["error"] = f"MC Iterations cannot exceed {MAX_MC_ITERATIONS}."
        return

    if return_method not in MC_RETURN_METHODS:
        st.session_state["error"] = (
            f"Unsupported Monte Carlo return method '{return_method}'. Expected one of: {', '.join(MC_RETURN_METHODS)}."
        )
        return

    def _update_progress(fraction: float) -> None:
        if progress_bar is not None:
            progress_bar.progress(fraction, text=f"Simulating... {fraction:.0%}")

    try:
        st.session_state["mc_running"] = True
        config = MonteCarloConfig(n_iterations=n_iterations, seed=seed, return_method=return_method)
        result = service.run_monte_carlo(
            scenario_id=st.session_state.get("scenario_id"),
            start_year=st.session_state.get("start_year"),
            end_year=st.session_state.get("end_year"),
            config=config,
            progress_callback=_update_progress,
        )
        st.session_state["mc_result"] = result
        st.session_state["mc_running"] = False
        st.session_state["error"] = None
    except Exception as exc:  # noqa: BLE001
        st.session_state["error"] = str(exc)
        st.session_state["mc_result"] = None
        st.session_state["mc_running"] = False


def apply_yaml_edits(yaml_text: str) -> None:
    """Parse edited YAML, rebuild service, and reproject only if one was active."""
    try:
        had_active_projection = st.session_state.get("projection") is not None
        yaml_size = len(yaml_text.encode("utf-8"))
        if yaml_size > MAX_YAML_SIZE_BYTES:
            st.session_state["yaml_edit_error"] = (
                f"YAML override error: content exceeds {MAX_YAML_SIZE_BYTES} bytes ({yaml_size} bytes provided)."
            )
            return

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as tmp:
            tmp.write(yaml_text)
            tmp_path = tmp.name

        service = PlanningService.from_yaml(tmp_path)
        st.session_state["service"] = service
        st.session_state["yaml_text"] = yaml_text
        st.session_state["yaml_applied"] = yaml_text
        st.session_state["projection"] = None
        st.session_state["mc_result"] = None
        st.session_state["mc_running"] = False
        st.session_state["error"] = None
        st.session_state["yaml_edit_error"] = None

        _set_scenario_and_year_controls(service)

        if had_active_projection:
            run_projection()
    except Exception as exc:  # noqa: BLE001
        st.session_state["yaml_edit_error"] = f"YAML override error: {exc}"
