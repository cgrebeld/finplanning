"""Overview section — summary metrics, gap chart and estate summary."""

import streamlit as st
from finplanning_core.engine import EstateCalculationStatus, ProjectionResult, calculate_projection_estate
from finplanning_core.services import PlanningService

from ..charts.gap_analysis import render_gap_chart
from ..components.summary_metrics import render_summary_metrics
from .monte_carlo import render_lines


def render_overview(projection: ProjectionResult, service: PlanningService) -> None:
    """Render the overview section with summary metrics, gap analysis chart and estate summary."""
    plan = service.manager.get_plan(projection.scenario_id)
    st.header(f"Overview: {plan.household.name}")
    render_summary_metrics(projection, plan)
    if projection.final_real_asset_value > 0:
        st.caption(
            f"Final net worth covers investment accounts only; real assets add "
            f"${projection.final_real_asset_value:,.0f} for a household total of "
            f"${projection.final_total_household_asset_value:,.0f}."
        )
    with st.expander("Market profile and assumptions"):
        render_lines("Material assumptions", plan.material_assumptions())
        render_lines("Defaulted inputs", projection.defaulted_inputs)
    st.divider()
    render_gap_chart(projection)
    st.divider()
    _render_estate_summary(projection, service)


def _render_estate_summary(projection: ProjectionResult, service: PlanningService) -> None:
    st.subheader(
        "Estate",
        help="The engine's estimate of the estate left after the last death at the end of the projection: "
        "deemed disposition and registered-account income on the final tax return, then probate, executor "
        "and administration costs. Settlements at an earlier death (when accounts don't roll over to the "
        "spouse) are shown separately and are already paid from the accounts during the projection.",
    )
    try:
        estate = calculate_projection_estate(service.manager.get_plan(projection.scenario_id), projection)
    except Exception as exc:  # noqa: BLE001 - an estate failure shouldn't hide the rest of the overview
        st.caption(f"Estate estimate unavailable: {exc}")
        return

    if estate.status != EstateCalculationStatus.CALCULATED:
        st.info("Estate estimate not supported for this plan: " + "; ".join(estate.unsupported_reasons))
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(f"Gross Estate ({estate.death_year})", f"${estate.gross_estate:,.0f}")
    col2.metric("Final-Return Tax", f"${estate.terminal_total_tax:,.0f}")
    col3.metric("Probate & Estate Costs", f"${estate.total_estate_costs:,.0f}")
    col4.metric(
        "After-Tax Estate",
        f"${estate.after_tax_nominal:,.0f}",
        help=f"${estate.after_tax_real:,.0f} in {estate.valuation_year} dollars.",
    )
    st.caption(
        f"Estate values are nominal at {estate.death_year}; the after-tax estate is "
        f"${estate.after_tax_real:,.0f} in {estate.valuation_year} dollars."
    )

    for yr in projection.years:
        if yr.estate_total_costs > 0 or yr.estate_settlement_tax > 0:
            st.caption(
                f"Settlement after an earlier death, paid in {yr.year}: tax ${yr.estate_settlement_tax:,.0f}, "
                f"OAS repayment ${yr.estate_settlement_oas_clawback:,.0f}, "
                f"probate and estate costs ${yr.estate_total_costs:,.0f}."
            )
    for warning in estate.warnings:
        st.caption(warning)
