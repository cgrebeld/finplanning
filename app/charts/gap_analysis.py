"""Gap analysis chart — first-year spending versus first-year spending capacity."""

import plotly.graph_objects as go
import streamlit as st
from finplanning_core.engine import ProjectionResult

_HELP = (
    "Compares this year's ongoing spending (excluding one-time and recurring lump sums) with "
    "first-year spending capacity: the most the plan can fund if the same inflation-adjusted amount "
    "is added to or removed from every year of your existing expense schedule (its spending curve, "
    "category inflation and end dates are kept) without running out and while keeping the terminal "
    "reserve. It is a deterministic projection, not a probability of success or a safe spending amount."
)


def capacity_label(projection: ProjectionResult) -> str | None:
    """Capacity as the engine resolved it, or None when there is no amount to show."""
    status = projection.sustainable_spending_status
    if status == "FOUND":
        return f"${projection.sustainable_spending:,.0f}"
    if status == "UPPER_BOUND_NOT_FOUND":
        return f"At least ${projection.sustainable_spending:,.0f}"
    return None


def capacity_note(projection: ProjectionResult) -> str:
    """Status and dollar basis of the capacity figure."""
    dollars = f"{projection.valuation_year} dollars"
    match projection.sustainable_spending_status:
        case "FOUND":
            return f"Deterministic first-year capacity in {dollars}."
        case "UPPER_BOUND_NOT_FOUND":
            return f"The search reached its cap before finding a limit, so capacity is only a lower bound ({dollars})."
        case "INFEASIBLE_AT_ZERO":
            return (
                "The plan depletes or misses its terminal reserve even with no ongoing spending, so there is "
                "no spending capacity to show."
            )
        case status:
            return f"Spending capacity was not evaluated (status {status})."


def render_gap_chart(projection: ProjectionResult) -> None:
    """Render a horizontal bar chart comparing desired spending with spending capacity."""
    st.subheader("Spending Gap Analysis", help=_HELP)
    label = capacity_label(projection)
    if label is None:
        st.warning(capacity_note(projection))
        return

    d = projection.desired_spending
    s = projection.sustainable_spending
    gap = s - d
    gap_color = "green" if gap >= 0 else "red"
    gap_label = f"Surplus ${abs(gap):,.0f}" if gap >= 0 else f"Shortfall ${abs(gap):,.0f}"
    if projection.sustainable_spending_status != "FOUND":
        gap_label = f"Surplus at least ${gap:,.0f}"

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=["Spending"],
            x=[s],
            name="First-year spending capacity",
            orientation="h",
            marker_color="mediumseagreen",
            text=[label],
            textposition="inside",
            insidetextanchor="middle",
        )
    )
    fig.add_trace(
        go.Bar(
            y=["Spending"],
            x=[d],
            name="Desired (first year)",
            orientation="h",
            marker_color="steelblue",
            text=[f"${d:,.0f}"],
            textposition="inside",
            insidetextanchor="middle",
        )
    )
    fig.add_annotation(
        x=max(d, s) * 1.02,
        y="Spending",
        text=f"<b>{gap_label}</b>",
        showarrow=False,
        font={"size": 14, "color": gap_color},
        xanchor="left",
    )
    fig.update_layout(
        xaxis_title=f"Annual Spending ({projection.valuation_year} $)",
        xaxis_tickprefix="$",
        xaxis_tickformat=",.0f",
        barmode="group",
        height=180,
        margin={"t": 40, "b": 40, "l": 80, "r": 120},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )

    st.plotly_chart(fig, width="stretch")
    st.caption(capacity_note(projection))
