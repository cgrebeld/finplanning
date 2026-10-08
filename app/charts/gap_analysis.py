"""Gap analysis chart — first-year spending versus first-year spending capacity."""

import plotly.graph_objects as go
import streamlit as st


def render_gap_chart(desired: float, sustainable: float) -> None:
    """Render a horizontal bar chart comparing desired spending with spending capacity.

    ``sustainable`` is the engine's first-year spending capacity: desired spending plus the
    largest constant-real adjustment to the existing expense schedule the plan can fund.
    """
    d = desired
    s = sustainable
    gap = s - d
    gap_color = "green" if gap >= 0 else "red"
    gap_label = f"Surplus ${abs(gap):,.0f}" if gap >= 0 else f"Shortfall ${abs(gap):,.0f}"

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=["Spending"],
            x=[s],
            name="First-year spending capacity",
            orientation="h",
            marker_color="mediumseagreen",
            text=[f"${s:,.0f}"],
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

    # Gap annotation
    fig.add_annotation(
        x=max(d, s) * 1.02,
        y="Spending",
        text=f"<b>{gap_label}</b>",
        showarrow=False,
        font={"size": 14, "color": gap_color},
        xanchor="left",
    )

    st.subheader(
        "Spending Gap Analysis",
        help="Compares this year's ongoing spending (excluding one-time and recurring lump sums) with "
        "first-year spending capacity: the most the plan can fund if the same inflation-adjusted amount "
        "is added to or removed from every year of your existing expense schedule (its retirement "
        "spending curve, category inflation and end dates are kept) without running out and while "
        "keeping the terminal reserve. It is a deterministic projection, not a probability of success. "
        "A green gap means the schedule is fully funded; a red gap indicates a shortfall.",
    )
    fig.update_layout(
        xaxis_title="Annual Spending ($)",
        xaxis_tickprefix="$",
        xaxis_tickformat=",.0f",
        barmode="group",
        height=180,
        margin={"t": 40, "b": 40, "l": 80, "r": 120},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )

    st.plotly_chart(fig, width="stretch")
