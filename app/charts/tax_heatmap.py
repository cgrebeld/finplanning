"""Tax heat map — colour-coded grid showing marginal tax rate by age."""

import plotly.graph_objects as go
import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan

from ..state import select_year, year_for_selected_age


def build_tax_heatmap_figure(
    projection: ProjectionResult, plan: HouseholdPlan, selected_year: int | None = None
) -> go.Figure:
    """Render a heat map of marginal and average tax rates over time.

    Darker cells = higher tax rate.  Helps identify RRSP meltdown
    opportunities (years where the MTR temporarily dips).
    """
    person1_name = plan.household.person1.name.split()[0]
    ages = [yr.person1_age for yr in projection.years]
    years = [yr.year for yr in projection.years]
    mtr = [float(yr.marginal_tax_rate * 100) for yr in projection.years]
    avg = [float(yr.average_tax_rate * 100) for yr in projection.years]

    fig = go.Figure()

    fig.add_trace(
        go.Heatmap(
            x=ages,
            y=["Avg Tax Rate", "Marginal Tax Rate"],
            z=[avg, mtr],
            customdata=[years, years],
            colorscale=[
                [0.0, "lightyellow"],
                [0.3, "gold"],
                [0.6, "orangered"],
                [1.0, "darkred"],
            ],
            colorbar={"title": "Rate %", "ticksuffix": "%"},
            hoverinfo="skip",
        )
    )
    # Heatmaps aren't selectable in plotly, so invisible markers over each cell carry the
    # hover text and make the cells clickable.
    for label, rates in (("Avg Tax Rate", avg), ("Marginal Tax Rate", mtr)):
        fig.add_trace(
            go.Scatter(
                x=ages,
                y=[label] * len(ages),
                customdata=list(zip(years, rates, strict=True)),
                mode="markers",
                marker={"size": 18, "symbol": "square", "opacity": 0},
                showlegend=False,
                hovertemplate=(
                    f"{person1_name} is %{{x}}: %{{customdata[0]}}<br>{label}: %{{customdata[1]:.1f}}%<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        xaxis_title=f"{person1_name} Age",
        xaxis_dtick=5,
        yaxis={"autorange": "reversed"},
        height=200,
        margin={"t": 40, "b": 60, "l": 120, "r": 20},
    )

    if selected_year is not None:
        selected = next((yr for yr in projection.years if yr.year == selected_year), None)
        if selected is not None:
            fig.add_vline(
                x=selected.person1_age,
                line_dash="solid",
                line_color="#ff4da6",
                line_width=3,
            )

    return fig


def render_tax_heatmap(projection: ProjectionResult, plan: HouseholdPlan, selected_year: int | None = None) -> None:
    st.subheader(
        "Tax Rate Heat Map",
        help="Colour-coded grid showing marginal and average federal and provincial tax rates by age. "
        "Darker colours indicate higher rates. Use this to identify years where tax-efficient "
        "withdrawal strategies could reduce your overall tax burden. Click a cell to select that year.",
    )
    fig = build_tax_heatmap_figure(projection, plan, selected_year=selected_year)
    event = st.plotly_chart(fig, width="stretch", key="tax_heatmap", on_select="rerun", selection_mode="points")
    select_year(year_for_selected_age(projection, event.selection.points))
