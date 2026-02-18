"""Summary KPI metric cards."""

from __future__ import annotations

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult


def render_summary_metrics(projection: ProjectionResult) -> None:
    """Render 4 KPI metric cards across columns."""
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Final Net Worth", f"${projection.final_net_worth:,.0f}")

    with col2:
        depletion = f"Age {projection.depletion_age}" if projection.depletion_age else "Never"
        st.metric("Depletion Age", depletion)

    with col3:
        st.metric("Projection Years", str(len(projection.years)))

    with col4:
        first_withdrawal_year: str | None = None
        for yr in projection.years:
            if yr.total_withdrawals > 0:
                first_withdrawal_year = str(yr.year)
                break
        st.metric("First Withdrawal Year", first_withdrawal_year or "None needed")
