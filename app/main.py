"""Canadian Financial Planner — Streamlit entry point.

Launch with: streamlit run app/main.py

The __name__ guard prevents this module's UI code from executing when
ProcessPoolExecutor "spawn" workers re-import __main__ on macOS.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repo root is on sys.path so "from app.*" imports work.
# Streamlit adds the script's parent dir (app/) to sys.path, not the repo root.
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.services.planning import PlanningService

from app.components.sidebar import render_sidebar
from app.state import init_state
from app.views.cash_flow import render_cash_flow
from app.views.data_export import render_data_export
from app.views.edit_plan import render_edit_plan_view
from app.views.monte_carlo_section import render_monte_carlo_section
from app.views.net_worth_view import render_net_worth
from app.views.overview import render_overview
from app.views.tax_analysis import render_tax_analysis


def _apply_global_styles() -> None:
    """Inject all global CSS — padding, metric sizing, pink slider, red primary button."""
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 3rem;
            padding-bottom: 0.5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        div[data-testid="metric-container"] label[data-testid="stMetricLabel"] > div {
            font-size: 20px !important;
        }
        [data-testid="stMetricValue"] {
            font-size: 20px !important;
        }
        div[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
            background-color: #ff4da6 !important;
            border-color: #ff4da6 !important;
        }
        div[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div {
            background: #ff4da6 !important;
        }
        button[kind="primary"] {
            background-color: #dc3545 !important;
            border-color: #dc3545 !important;
        }
        button[kind="primary"]:hover {
            background-color: #c82333 !important;
            border-color: #bd2130 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_landing_page() -> None:
    """Render the feature-grid welcome screen shown before any plan is loaded."""
    st.title("Canadian Financial Planner")
    st.markdown(
        "Model your financial future — income, taxes, investments, and spending "
        "— across any time horizon."
    )
    st.markdown("")

    features = [
        ("📊", "Cash-Flow Projections", "Year-by-year income, expenses, taxes, and net worth"),
        ("⚖️", "Gap Analysis", "Compare desired vs. sustainable spending over your plan horizon"),
        ("📈", "Net Worth Tracking", "Watch account balances evolve across your full financial horizon"),
        ("🔀", "Sankey Diagrams", "Visualize where money comes from and where it goes, year by year"),
        ("🔥", "Tax Heatmaps", "See marginal and effective tax rates across your entire plan"),
        ("🎲", "Monte Carlo", "Stress-test your plan with thousands of randomized return scenarios"),
        ("🔬", "Scenario Comparison", "Clone and tweak plans to explore 'what if' alternatives"),
        ("📥", "Excel Export", "Download full projections as a detailed XLSX workbook"),
    ]

    row1_cols = st.columns(4)
    for col, (icon, name, desc) in zip(row1_cols, features[:4]):
        with col:
            with st.container(border=True):
                st.markdown(f"**{icon} {name}**")
                st.caption(desc)

    row2_cols = st.columns(4)
    for col, (icon, name, desc) in zip(row2_cols, features[4:]):
        with col:
            with st.container(border=True):
                st.markdown(f"**{icon} {name}**")
                st.caption(desc)

    st.markdown("")
    st.caption(
        "Supports CPP/OAS benefits, RRIF conversions, glide-path asset allocation, "
        "and full federal + provincial (BC) tax modelling with bracket indexation."
    )
    st.info("← Click **Load** to upload a plan file, or **Load Sample** to try a bundled example.", icon="👈")


if __name__ == "__main__":
    st.set_page_config(page_title="Canadian Financial Planner", layout="wide")

    _apply_global_styles()

    init_state()

    # Apply pending auto-navigation before widgets render so the sidebar
    # radio picks up the correct value in this same run.
    pending_nav = st.session_state.pop("_nav_after_run", None)
    if pending_nav is not None:
        st.session_state["nav_section"] = pending_nav

    render_sidebar()

    error: str | None = st.session_state.get("error")
    if error:
        st.error(error)

    projection_for_warnings: ProjectionResult | None = st.session_state.get("projection")
    for w in getattr(projection_for_warnings, "warnings", []):
        st.warning(w)

    service: PlanningService | None = st.session_state.get("service")
    if service is None:
        _render_landing_page()
        st.stop()

    nav_section = st.session_state.get("nav_section", "Edit Plan")

    if nav_section == "Edit Plan":
        render_edit_plan_view()
        st.stop()

    projection: ProjectionResult | None = st.session_state.get("projection")
    if projection is None:
        st.info("Go to **Edit Plan** and click **Run Projection** to generate results.")
        st.stop()

    # Dispatch to projection-required sections.
    if nav_section == "Monte Carlo":
        render_monte_carlo_section()
    else:
        _RENDERERS = {
            "Overview": render_overview,
            "Cash Flow": render_cash_flow,
            "Net Worth": render_net_worth,
            "Tax Analysis": render_tax_analysis,
            "Data & Export": render_data_export,
        }
        renderer = _RENDERERS.get(nav_section)
        if renderer is None:
            st.error(f"Unknown section: {nav_section!r}")
            st.stop()
        renderer(projection, service)
