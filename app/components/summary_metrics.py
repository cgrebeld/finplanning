"""Summary KPI metric cards."""

import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan


def depletion_text(projection: ProjectionResult) -> str:
    """Depletion year, or the horizon actually projected — never an unqualified 'Never'."""
    if projection.depletion_year is not None:
        return str(projection.depletion_year)
    return f"None through {projection.years[-1].year}" if projection.years else "Not projected"


def render_summary_metrics(projection: ProjectionResult, plan: HouseholdPlan) -> None:
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
            "Depletion Year",
            depletion_text(projection),
            help="Deterministic projection only; see Monte Carlo for the probability of depletion.",
        )
        if projection.depletion_ages_by_person:
            ages = "; ".join(
                f"{person.name}: age {projection.depletion_ages_by_person[person.id]}"
                for person in plan.persons
                if person.id in projection.depletion_ages_by_person
            )
            st.caption(f"Alive at depletion — {ages}.")

    with col4:
        first_yr = next((yr for yr in projection.years if yr.total_withdrawals > 0), None)
        st.metric("First Withdrawal Year", str(first_yr.year) if first_yr is not None else "None needed")
