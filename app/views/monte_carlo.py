"""Monte Carlo results view — fan chart with percentile bands and depletion metrics."""

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from finplanning_core.models.plan import HouseholdPlan
from finplanning_core.risk.monte_carlo import MonteCarloResult


def render_monte_carlo_view(result: MonteCarloResult, plan: HouseholdPlan) -> None:
    """Render Monte Carlo simulation results: metrics and fan chart."""
    _render_metrics(result)
    st.divider()
    _render_fan_chart(result, plan)


def _render_metrics(result: MonteCarloResult) -> None:
    """Show key simulation statistics as metric cards."""
    prob_pct = float(result.depletion_probability) * 100

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Depletion Probability", f"{prob_pct:.1f}%")
    with col2:
        age_str = str(result.median_depletion_age) if result.median_depletion_age is not None else "Never"
        st.metric("Median Depletion Age (Depleting Paths)", age_str)
    with col3:
        st.metric("Median Final Net Worth", _fmt(result.percentiles.get(50, 0.0)))
    with col4:
        st.metric("Simulations", f"{result.n_iterations:,}")


def _render_fan_chart(result: MonteCarloResult, plan: HouseholdPlan) -> None:
    """Draw a fan chart of net worth percentile bands from sample paths."""
    percentile_keys = (10, 25, 50, 75, 90)
    has_all_path_percentiles = (
        bool(result.net_worth_percentiles_by_year)
        and bool(result.person1_ages)
        and all(key in result.net_worth_percentiles_by_year for key in percentile_keys)
    )

    if not has_all_path_percentiles and not result.sample_paths:
        st.info("No paths available for fan chart.")
        return

    person1_name = plan.household.person1.name.split()[0]
    if has_all_path_percentiles:
        ages = result.person1_ages
        p10 = list(result.net_worth_percentiles_by_year[10])
        p25 = list(result.net_worth_percentiles_by_year[25])
        p50 = list(result.net_worth_percentiles_by_year[50])
        p75 = list(result.net_worth_percentiles_by_year[75])
        p90 = list(result.net_worth_percentiles_by_year[90])
        years = [[year] for year in result.projection_years]
    else:
        n_years = len(result.sample_paths[0].years)
        if n_years == 0:
            return

        ages = [result.sample_paths[0].years[t].person1_age for t in range(n_years)]

        # Fallback for legacy result objects with only sample paths.
        nw_matrix: list[list[float]] = []
        for path in result.sample_paths:
            nw_matrix.append([path.years[t].total_net_worth for t in range(n_years)])
        nw_arr = np.array(nw_matrix)
        p10 = np.percentile(nw_arr, 10, axis=0).tolist()
        p25 = np.percentile(nw_arr, 25, axis=0).tolist()
        p50 = np.percentile(nw_arr, 50, axis=0).tolist()
        p75 = np.percentile(nw_arr, 75, axis=0).tolist()
        p90 = np.percentile(nw_arr, 90, axis=0).tolist()
        years = [[result.sample_paths[0].years[t].year] for t in range(n_years)]
    hover = f"{person1_name} is %{{x}}: %{{customdata[0]}}<br>"

    fig = go.Figure()

    # 10th-90th band (lightest)
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=p90,
            customdata=years,
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hovertemplate=hover + "90th: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=p10,
            customdata=years,
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(68, 114, 196, 0.15)",
            name="10th–90th",
            hovertemplate=hover + "10th: $%{y:,.0f}<extra></extra>",
        )
    )

    # 25th-75th band (medium)
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=p75,
            customdata=years,
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hovertemplate=hover + "75th: $%{y:,.0f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=p25,
            customdata=years,
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor="rgba(68, 114, 196, 0.35)",
            name="25th–75th",
            hovertemplate=hover + "25th: $%{y:,.0f}<extra></extra>",
        )
    )

    # Median line
    fig.add_trace(
        go.Scatter(
            x=ages,
            y=p50,
            customdata=years,
            mode="lines",
            line={"color": "rgb(68, 114, 196)", "width": 2.5},
            name="Median",
            hovertemplate=hover + "Median: $%{y:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Net Worth Distribution",
        xaxis_title=f"{person1_name} Age",
        yaxis_title="Net Worth ($)",
        yaxis_tickprefix="$",
        yaxis_tickformat=",.0f",
        xaxis_dtick=5,
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
        height=500,
    )

    st.plotly_chart(fig, width="stretch")


def _fmt(value: float) -> str:
    return f"${value:,.0f}"
