"""Summary KPI metric cards."""

import streamlit as st
from finplanning_core.engine import ProjectionResult


def depletion_text(projection: ProjectionResult) -> str:
    """Depletion age, or the horizon actually projected — never an unqualified 'Never'."""
    if projection.depletion_age is not None:
        return f"Age {projection.depletion_age}"
    return f"None through {projection.years[-1].year}" if projection.years else "Not projected"


def render_summary_metrics(projection: ProjectionResult) -> None:
    """Render 4 KPI metric cards across columns."""
    end_year = projection.years[-1].year if projection.years else None
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            f"Final Liquid Net Worth ({end_year})",
            f"${projection.final_net_worth:,.0f}",
            help="Investment accounts only, in nominal dollars at the end of the projection.",
        )

    with col2:
        st.metric(
            "Final Household Assets",
            f"${projection.final_total_household_asset_value:,.0f}",
            help="Liquid net worth plus the gross market value of real assets, in nominal dollars.",
        )

    with col3:
        st.metric(
            "Depletion Age",
            depletion_text(projection),
            help="Deterministic projection only; see Monte Carlo for the probability of depletion.",
        )

    with col4:
        first_yr = next((yr for yr in projection.years if yr.total_withdrawals > 0), None)
        st.metric("First Withdrawal Year", str(first_yr.year) if first_yr is not None else "None needed")
