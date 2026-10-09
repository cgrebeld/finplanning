"""Net worth trajectory chart — stacked area showing account type balances over time."""

import plotly.graph_objects as go
import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan

from ..state import select_year, year_for_selected_age


def build_net_worth_figure(
    projection: ProjectionResult, plan: HouseholdPlan, selected_year: int | None = None
) -> go.Figure:
    """Build a stacked area chart of Non-Reg, RRSP/RRIF, and TFSA balances, plus real assets if any."""
    person1_name = plan.household.person1.name.split()[0]
    ages = [yr.person1_age for yr in projection.years]
    years = [yr.year for yr in projection.years]
    non_reg = [float(yr.total_non_reg) for yr in projection.years]
    rrsp_rrif = [float(yr.total_rrsp_rrif) for yr in projection.years]
    tfsa = [float(yr.total_tfsa) for yr in projection.years]

    hover = f"{person1_name} is %{{x}}: %{{customdata}}<br>"

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=ages,
            y=non_reg,
            customdata=years,
            name="Non-Registered",
            mode="lines+markers",
            stackgroup="one",
            line={"width": 0.5},
            marker={"size": 14, "opacity": 0},
            hovertemplate=hover + "Non-Reg: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=rrsp_rrif,
            customdata=years,
            name="RRSP / RRIF",
            mode="lines+markers",
            stackgroup="one",
            line={"width": 0.5},
            marker={"size": 14, "opacity": 0},
            hovertemplate=hover + "RRSP/RRIF: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=tfsa,
            customdata=years,
            name="TFSA",
            mode="lines+markers",
            stackgroup="one",
            line={"width": 0.5},
            marker={"size": 14, "opacity": 0},
            hovertemplate=hover + "TFSA: $%{y:,.0f}<extra></extra>",
        )
    )

    real_assets = [float(yr.total_real_asset_value) for yr in projection.years]
    if any(real_assets):
        fig.add_trace(
            go.Scatter(
                x=ages,
                y=real_assets,
                customdata=years,
                name="Real Assets",
                mode="lines+markers",
                stackgroup="one",
                line={"width": 0.5},
                marker={"size": 14, "opacity": 0},
                hovertemplate=hover + "Real Assets: $%{y:,.0f}<extra></extra>",
            )
        )

    # The account traces carry invisible markers because plotly only click-selects traces with
    # markers (and only the first hovered trace). This trace adds the total to the unified hover.
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=[float(yr.total_net_worth + yr.total_real_asset_value) for yr in projection.years],
            customdata=years,
            name="Total",
            mode="markers",
            marker={"size": 14, "opacity": 0},
            showlegend=False,
            hovertemplate="<b>Total: $%{y:,.0f}</b><extra></extra>",
        )
    )

    birth_year = plan.household.person1.birth_date.year

    if plan.assumptions.black_swan is not None:
        trigger_age = plan.assumptions.black_swan.trigger_year - birth_year
        fig.add_vline(
            x=trigger_age,
            line_dash="dash",
            line_color="gold",
            annotation={"text": "🦢 Black Swan", "textangle": -45, "yanchor": "bottom"},
        )

    for event in plan.one_time_events:
        event_age = event.year - birth_year
        emoji = "🟢↑ " if event.event_type == "income" else "🔴↓ " if event.event_type == "expense" else ""
        fig.add_vline(
            x=event_age,
            line_dash="dot",
            line_color="dodgerblue",
            annotation={"text": f"{emoji}{event.name}", "textangle": -45, "yanchor": "bottom"},
        )

    if projection.depletion_age is not None:
        for yr in projection.years:
            if yr.total_net_worth <= 0:
                fig.add_vline(
                    x=yr.person1_age,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="Depletion",
                    annotation_position="top left",
                )
                break

    if selected_year is not None:
        selected = next((yr for yr in projection.years if yr.year == selected_year), None)
        if selected is not None:
            fig.add_vline(
                x=selected.person1_age,
                line_dash="solid",
                line_color="magenta",
                annotation_text=str(selected.year),
                annotation_position="top right",
            )

    fig.update_layout(
        xaxis_title=f"{person1_name} Age",
        yaxis_title="Balance (nominal $)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        xaxis_dtick=5,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        height=450,
    )

    return fig


def render_net_worth_chart(projection: ProjectionResult, plan: HouseholdPlan, selected_year: int | None = None) -> None:
    """Render net worth chart using externally selected year state."""
    st.subheader(
        "Net Worth by Account Type",
        help="Stacked area chart showing projected balances for Non-Registered, RRSP/RRIF, and TFSA "
        "accounts over time, plus the market value of real assets (property) when the plan has any. "
        "Depletion refers to the investment accounts only. The magenta line marks the currently selected year; "
        "click the chart to select a different year. Hover to see individual account values at each age.",
    )
    fig = build_net_worth_figure(projection, plan, selected_year=selected_year)
    event = st.plotly_chart(fig, width="stretch", key="net_worth_chart", on_select="rerun", selection_mode="points")
    select_year(year_for_selected_age(projection, event.selection.points))
