"""Financial Planner Helper — Streamlit UI module.

Launch with: streamlit run streamlit_app.py

The __name__ guard prevents this module's UI code from executing when
ProcessPoolExecutor "spawn" workers re-import __main__ on macOS.
"""

import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.services import PlanningService

from .components.sidebar import render_sidebar
from .state import init_state
from .views.cash_flow import render_cash_flow
from .views.data_export import render_data_export
from .views.edit_plan import render_edit_plan_view
from .views.monte_carlo_section import render_monte_carlo_section
from .views.net_worth_view import render_net_worth
from .views.overview import render_overview
from .views.tax_analysis import render_tax_analysis


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
        .app-version {
            position: fixed;
            bottom: 0.75rem;
            left: 1rem;
            font-size: 0.7rem;
            color: rgba(150, 150, 150, 0.55);
            font-family: monospace;
            pointer-events: none;
        }
        /* Pager buttons: left-align text.
           Streamlit renders button[kind="tertiary"] content inside an inner
           <div> and <span> that both default to justify-content:center.
           Targeting the direct child div and its span overrides that centering. */
        button[kind="tertiary"] > div {
            justify-content: flex-start !important;
        }
        button[kind="tertiary"] > div > span {
            justify-content: flex-start !important;
        }
        /* Pager entries: reduce vertical spacing to ~4 px.
           st.container(height=...) renders a stVerticalBlock with the HTML
           attribute overflow="auto".  That element carries a 16px flex gap
           between entries; we shrink it to 0.25rem (~4 px). */
        [data-testid="stVerticalBlock"][overflow="auto"] {
            gap: 0.01rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_landing_page() -> None:
    """Render the feature-grid welcome screen shown before any plan is loaded."""
    st.title("Financial Planning Helper")
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


def run_app() -> None:
    """Render the Streamlit application."""
    st.set_page_config(page_title="Financial Planning Helper", layout="wide")

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
        st.info("Click **Run Projection** in the side bar to generate results.")
        st.stop()

    # Dispatch to projection-required sections.
    match nav_section:
        case "Monte Carlo":
            render_monte_carlo_section()
        case "Overview":
            render_overview(projection, service)
        case "Cash Flow":
            render_cash_flow(projection, service)
        case "Net Worth":
            render_net_worth(projection, service)
        case "Tax Analysis":
            render_tax_analysis(projection, service)
        case "Data & Export":
            render_data_export(projection, service)
        case _:
            st.error(f"Unknown section: {nav_section!r}")
            st.stop()


if __name__ == "__main__":
    run_app()
