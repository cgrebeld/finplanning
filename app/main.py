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

import tempfile
from pathlib import Path

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.risk.monte_carlo import MonteCarloResult
from finplanning_core.services.export import (
    header_labels_for_plan,
    rows_for_summary_output,
    rows_for_tabular_output,
    write_xlsx,
)
from finplanning_core.services.planning import PlanningService

from app.charts.cash_flow_sankey import render_cash_flow_sankey
from app.charts.gap_analysis import render_gap_chart
from app.charts.net_worth import render_net_worth_chart
from app.charts.tax_heatmap import render_tax_heatmap
from app.components.sidebar import render_sidebar
from app.components.summary_metrics import render_summary_metrics
from app.components.year_grid import render_year_grid
from app.state import (
    MC_RETURN_METHODS,
    MonteCarloReturnMethod,
    get_selected_flow_year,
    init_state,
    run_monte_carlo,
    set_selected_flow_year,
)
from app.views.monte_carlo import render_monte_carlo_view

if __name__ == "__main__":
    st.set_page_config(page_title="Canadian Financial Planner", layout="wide")

    init_state()

    render_sidebar()

    # --- Main area ---

    error: str | None = st.session_state.get("error")
    if error:
        st.error(error)

    projection_for_warnings: ProjectionResult | None = st.session_state.get("projection")
    for w in getattr(projection_for_warnings, "warnings", []):
        st.warning(w)

    service: PlanningService | None = st.session_state.get("service")
    if service is None:
        st.header("Canadian Financial Planner")
        st.markdown(
            """
A comprehensive retirement projection tool for Canadian households.

**Load a YAML plan from the sidebar to get started.** Your plan defines income sources,
accounts (RRSP, TFSA, non-registered), expenses, and assumptions — the engine does the rest.

**What you get:**
- **Cash-flow projections** — year-by-year income, expenses, taxes, withdrawals, and net worth
- **Gap analysis** — compare desired vs. sustainable spending levels
- **Interactive net worth chart** — track account balances across your full retirement horizon
- **Cash-flow Sankey diagrams** — visualize money flows for any selected year
- **Tax heatmaps** — see marginal and effective tax rates over time
- **Monte Carlo simulation** — stress-test your plan with thousands of randomized return scenarios
- **Scenario comparison** — clone and tweak plans to compare "what if" alternatives
- **Excel export** — download detailed projections as an XLSX workbook

Supports CPP/OAS benefits, RRIF conversions, glide-path asset allocation, and full
federal + provincial (BC) tax modelling with bracket indexation.
"""
        )
        st.stop()

    projection: ProjectionResult | None = st.session_state.get("projection")
    if projection is None:
        st.header("Canadian Financial Planner")
        st.write("Click **Run Projection** in the sidebar to generate results.")
        st.stop()

    # --- Results ---

    st.header(f"Projection: {service.plan.household.name}")

    render_summary_metrics(projection)

    # st.divider()

    render_gap_chart(projection.desired_spending, projection.sustainable_spending)

    # st.divider()

    selected_flow_year = get_selected_flow_year(projection)
    render_net_worth_chart(projection, service.plan, selected_year=selected_flow_year)

    # st.divider()

    years = [year.year for year in projection.years]
    slider_key = "selected_flow_year_slider"
    st.session_state[slider_key] = selected_flow_year

    def _on_selected_year_slider_change() -> None:
        slider_year_value = st.session_state.get(slider_key)
        if isinstance(slider_year_value, int):
            set_selected_flow_year(slider_year_value)

    st.markdown(
        """
        <style>
        /* top block */
        .block-container {
            padding-top: 3rem;
            padding-bottom: 0.5rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        div[data-testid="metric-container"] label[data-testid="stMetricLabel"] > div {
            font-size: 20px !important;  /* label size */
        }
        [data-testid="stMetricValue"] {
            font-size: 20px !important;  /* value size */
        }
        div[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"] {
            background-color: #ff4da6 !important;
            border-color: #ff4da6 !important;
        }
        div[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div {
            background: #ff4da6 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    sankey_col1, _ = st.columns([2, 1])
    with sankey_col1:
        slider_year = st.slider(
            "Select Year",
            min_value=min(years),
            max_value=max(years),
            step=1,
            key=slider_key,
            on_change=_on_selected_year_slider_change,
            help="Use this slider to choose the year shown in the cash flow diagram.",
        )
    selected_flow_year = int(slider_year)
    sankey_zoom_scale = 1.0

    render_cash_flow_sankey(projection, service.plan, selected_flow_year, zoom_scale=sankey_zoom_scale)

    # --- Monte Carlo ---

    st.header(
        "Monte Carlo Simulation",
        help="Runs thousands of projections using randomised investment returns to stress-test your plan. "
        "Results show the probability of depleting your portfolio, median outcomes, and the range of "
        "possible net worth paths across percentile bands.",
    )

    st.markdown(
        """
        <style>
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

    mc_lbl1, mc_lbl2, mc_lbl3, mc_lbl4 = st.columns(4)
    mc_lbl1.markdown("")  # Empty label for button column
    mc_lbl2.markdown(
        "**Iterations** :grey_question:",
        help="Number of random simulations to run. Higher values produce more stable results "
        "but take longer. Choose 500 for quick tests, 1,000 for standard analysis, or 2,000 for more precision.",
    )
    mc_lbl3.markdown(
        "**Method** :grey_question:",
        help=(
            "**historical**\n"
            "- 5-year block bootstrap from US returns 1928-2024\n"
            "- Resamples equity, fixed income & cash together\n"
            "- Preserves cross-asset correlation & autocorrelation\n"
            "- Includes real crashes (1931, 2008, etc.)\n\n"
            "**parametric**\n"
            "- Fat-tailed Student's t-distribution (df=5)\n"
            "- Randomises equity only; fixed income & cash use plan defaults\n"
            "- Scaled to plan's mean/std assumptions\n\n"
            "One-time events and recurring expenses are applied in every iteration. "
            "Custom black swan shocks are not applied — return paths already capture extremes."
        ),
    )
    mc_lbl4.markdown(
        "**Seed** :grey_question:",
        help="Random seed for reproducible simulations. Use the same seed to get identical results. "
        "Leave blank or set to 0 for a different random result each time.",
    )
    mc_btn_col, mc_iter_col, mc_method_col, mc_seed_col = st.columns(4)
    with mc_iter_col:
        mc_iterations = st.selectbox(
            "Iterations",
            options=[500, 1000, 2000],
            index=1,
            label_visibility="collapsed",
        )
    with mc_method_col:
        mc_return_method = st.selectbox(
            "Return Method",
            options=MC_RETURN_METHODS,
            index=0,
            label_visibility="collapsed",
            help=(
                "historical: 5-year block bootstrap from US returns 1928-2024 (equity, fixed income, cash). "
                "parametric: equity-only fat-tailed t-distribution (df=5) using plan assumptions."
            ),
        )
        if mc_return_method not in MC_RETURN_METHODS:
            st.session_state["error"] = f"Unsupported Monte Carlo return method: {mc_return_method!r}"
            st.stop()
        selected_return_method: MonteCarloReturnMethod = mc_return_method
    with mc_seed_col:
        mc_seed_input = st.number_input(
            "Seed",
            min_value=0,
            max_value=999999,
            value=42,
            step=1,
            label_visibility="collapsed",
            help="Set to 0 for random seed",
        )
        mc_seed = int(mc_seed_input) if mc_seed_input > 0 else None
    with mc_btn_col:
        mc_running = bool(st.session_state.get("mc_running"))
        if st.button(
            "Run",
            disabled=mc_running,
            type="primary",
            use_container_width=True,
            help="A Monte Carlo run is already in progress." if mc_running else None,
        ):
            mc_progress = st.progress(0.0, text="Simulating... 0%")
            run_monte_carlo(
                n_iterations=int(mc_iterations),
                seed=mc_seed,
                return_method=selected_return_method,
                progress_bar=mc_progress,
            )
            mc_progress.empty()

    mc_result: MonteCarloResult | None = st.session_state.get("mc_result")
    if mc_result is not None:
        render_monte_carlo_view(mc_result, service.plan)

    st.divider()

    render_tax_heatmap(projection, service.plan, selected_year=selected_flow_year)

    render_year_grid(projection, service.plan, selected_year=selected_flow_year)

    def _build_summary_xlsx() -> bytes:
        assert projection is not None
        assert service is not None
        rows = rows_for_summary_output(projection, service.plan)
        labels = {f: f for f in rows[0]}
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            write_xlsx(
                rows,
                tmp.name,
                header_labels=labels,
                chart_x_field="Year",
                chart_series=[("Net Worth", "Net Worth")],
            )
            return Path(tmp.name).read_bytes()

    def _build_detailed_xlsx() -> bytes:
        assert projection is not None
        assert service is not None
        account_ids = [acc.id for acc in service.plan.accounts]
        rows = rows_for_tabular_output(projection, account_ids)
        labels, series = header_labels_for_plan(list(rows[0].keys()), service.plan)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            write_xlsx(rows, tmp.name, header_labels=labels, chart_series=series)
            return Path(tmp.name).read_bytes()

    export_summary_col, export_detailed_col = st.columns(2)

    with export_summary_col:
        st.download_button(
            label="Export Summary",
            data=_build_summary_xlsx(),
            file_name="projection_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with export_detailed_col:
        st.download_button(
            label="Export Detailed",
            data=_build_detailed_xlsx(),
            file_name="projection_detailed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
