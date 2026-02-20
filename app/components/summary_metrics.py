"""Summary KPI metric cards."""

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult


def render_summary_metrics(projection: ProjectionResult) -> None:
    """Render 4 KPI metric cards across columns."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Final Net Worth", f"${projection.final_net_worth:,.0f}")

    with col2:
        depletion = f"Age {projection.depletion_age}" if projection.depletion_age is not None else "Never"
        st.metric("Depletion Age", depletion)

    with col3:
        st.metric("Projection Years", str(len(projection.years)))

    with col4:
        first_yr = next((yr for yr in projection.years if yr.total_withdrawals > 0), None)
        st.metric("First Withdrawal Year", str(first_yr.year) if first_yr is not None else "None needed")
