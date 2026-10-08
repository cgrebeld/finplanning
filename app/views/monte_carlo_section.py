"""Monte Carlo section — simulation controls and results."""

import streamlit as st
from finplanning_core.risk import MonteCarloResult
from finplanning_core.services import PlanningService

from ..state import (
    MC_RETURN_METHODS,
    MonteCarloReturnMethod,
    current_run_params,
    describe_run_params,
    run_monte_carlo,
)
from .monte_carlo import render_monte_carlo_view


def render_monte_carlo_section() -> None:
    """Render Monte Carlo simulation controls and results."""
    service: PlanningService | None = st.session_state.get("service")
    mc_result: MonteCarloResult | None = st.session_state.get("mc_result")

    st.header(
        "Monte Carlo Simulation",
        help=(
            "Runs up to 2,000 projections with randomised investment returns, inflation, housing prices and "
            "lifespans to stress-test your plan. Results show the probability of depleting your investment "
            "accounts, median outcomes, and the range of liquid net worth paths in start-year dollars."
        ),
    )

    mc_lbl1, mc_lbl2, mc_lbl3, mc_lbl4 = st.columns(4)
    mc_lbl1.markdown("")
    mc_lbl2.markdown(
        "**Iterations** :grey_question:",
        help=(
            "Number of random simulations to run. Higher values produce more stable results "
            "but take longer. Choose 500 for quick tests, 1,000 for standard analysis, or 2,000 for more precision."
        ),
    )
    profile = service.plan.market_profile if service is not None else None
    history = profile.description if profile is not None else "the plan's market profile history"
    mc_lbl3.markdown(
        "**Method** :grey_question:",
        help=(
            "**historical**\n"
            f"- 5-year block bootstrap of {history}\n"
            "- Each sampled year keeps every asset class and inflation together, preserving correlations\n"
            "- Recentred on the plan's return assumptions: history supplies volatility, not return levels\n\n"
            "**parametric**\n"
            "- Multivariate Student's t draws for every asset class and inflation, with the history's "
            "volatilities and correlations\n"
            "- Centred on the plan's return assumptions\n\n"
            "Fees are deducted once, in each account. One-time events and recurring expenses apply in every "
            "path; the deterministic black-swan shock does not."
        ),
    )
    mc_lbl4.markdown(
        "**Seed** :grey_question:",
        help=(
            "Random seed for reproducible simulations. Use the same seed to get identical results. "
            "Set to 0 for a different random result each time."
        ),
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
            help=f"historical: 5-year block bootstrap of {history}. parametric: multivariate t across all classes.",
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
            st.rerun()

    mc_result = st.session_state.get("mc_result")
    mc_params = st.session_state.get("mc_params")
    if mc_result is not None and mc_params is not None:
        if mc_params != current_run_params():
            st.warning(
                f"Showing a simulation of {describe_run_params(mc_params)}. The sidebar selection has "
                "changed — click **Run** to update."
            )
        else:
            st.caption(describe_run_params(mc_params))
    if mc_result is not None and service is not None:
        render_monte_carlo_view(mc_result, service.manager.get_plan(mc_result.scenario_id))
