"""Gap analysis chart — horizontal bar comparing desired vs sustainable spending."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st


def render_gap_chart(desired: float, sustainable: float) -> None:
    """Render a horizontal bar chart comparing desired vs sustainable spending.

    Green bar for sustainable, red/green gap indicator depending on
    whether spending is fully funded.
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
            name="Sustainable",
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
            name="Desired",
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
        help="Compares your desired annual spending against the maximum sustainable spending level. "
        "A green gap means your plan is fully funded; a red gap indicates a shortfall that may "
        "require reduced spending or additional income.",
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

    st.plotly_chart(fig, width="container")
