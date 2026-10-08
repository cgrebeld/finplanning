"""Monte Carlo results view — status, depletion metrics, assumptions and the fan chart."""

from typing import Any

import numpy as np
import plotly.graph_objects as go
import streamlit as st
from finplanning_core.models import HouseholdPlan
from finplanning_core.risk import MonteCarloResult

_PERCENTILE_KEYS = (10, 25, 50, 75, 90)


def _percentiles(values: dict[int, float]) -> dict[str, float]:
    return {f"p{key}": round(value, 2) for key, value in sorted(values.items())}


def mc_summary(result: MonteCarloResult) -> dict[str, Any]:
    """Export-ready summary using the keys, units and null rules of the engine's ``run_monte_carlo`` tool JSON.

    An unsupported run has no depletion probability and no simulated paths, never zeros.
    """
    complete = result.status == "COMPLETE"
    return {
        "status": result.status,
        "unsupported_reasons": list(result.unsupported_reasons),
        "scenario_id": result.scenario_id,
        "n_iterations": result.n_iterations if complete else 0,
        "seed": result.seed,
        "depletion_probability": round(float(result.depletion_probability), 4) if complete else None,
        "depletion_probability_interval": (
            [round(v, 4) for v in result.depletion_probability_interval] if complete else []
        ),
        "median_depletion_age": result.median_depletion_age if complete else None,
        # Final liquid net worth at reporting_end_year, in valuation_year (start-year) dollars.
        "percentiles": _percentiles(result.percentiles) if complete else {},
        "net_worth_dollars": result.net_worth_dollars,
        "valuation_year": result.valuation_year,
        "reporting_end_year": result.reporting_end_year,
        "risk_end_year": result.risk_end_year,
        # Nominal at each path's ultimate death.
        "total_estate_costs_percentiles": _percentiles(result.total_estate_costs_percentiles) if complete else {},
        "return_method": result.return_method,
        "calibration_profile": result.calibration_profile,
        "calibration_version": result.calibration_version,
        "resolved_arithmetic_means": dict(result.resolved_arithmetic_means),
        "mortality_method": result.mortality_method,
        "housing_return_method": result.housing_return_method,
        "confidence_scope": result.confidence_scope,
        "defaulted_inputs": list(result.defaulted_inputs),
        "warnings": list(result.warnings),
    }


def depletion_scope_text(result: MonteCarloResult) -> str:
    """What was simulated, stated instead of an unqualified 'Never'."""
    paths = f"{result.n_iterations:,} simulated paths through {result.risk_end_year}"
    if result.median_depletion_age is not None:
        return f"Median age at depletion among the depleting paths of {paths}."
    return f"No path depleted in {paths}."


def render_monte_carlo_view(result: MonteCarloResult, plan: HouseholdPlan) -> None:
    """Render Monte Carlo simulation results: status, metrics, assumptions and fan chart."""
    if result.status != "COMPLETE":
        st.warning(
            f"Monte Carlo result is {result.status}: "
            + ("; ".join(result.unsupported_reasons) or "no reason given")
            + ". No probabilities or percentiles were simulated."
        )
        _render_assumptions(result, plan)
        return
    _render_metrics(result)
    _render_assumptions(result, plan)
    st.divider()
    _render_fan_chart(result, plan)


def _render_metrics(result: MonteCarloResult) -> None:
    """Show key simulation statistics as metric cards."""
    low, high = result.depletion_probability_interval
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            f"Depletion Probability (to {result.risk_end_year})",
            f"{result.depletion_probability:.1%}",
            help=f"95% interval {low:.1%}–{high:.1%} (sampling error only).",
        )
    with col2:
        age = result.median_depletion_age
        st.metric(
            "Median Depletion Age (Depleting Paths)",
            str(age) if age is not None else f"None of {result.n_iterations:,}",
            help=depletion_scope_text(result),
        )
    with col3:
        st.metric(
            f"Median Liquid Net Worth ({result.reporting_end_year})",
            _fmt(result.percentiles[50]) if 50 in result.percentiles else "n/a",
            help=f"Investment accounts only, in {result.valuation_year} dollars, frozen at an earlier household "
            "death. Excludes real assets.",
        )
    with col4:
        st.metric("Simulated Paths", f"{result.n_iterations:,}", help=f"Seed {result.seed}.")
    st.caption(
        f"{depletion_scope_text(result)} Liquid net worth is in {result.valuation_year} dollars through "
        f"{result.reporting_end_year}; depletion, death and estate outcomes run through {result.risk_end_year}. "
        f"Risks simulated: {result.confidence_scope}."
    )


def _render_assumptions(result: MonteCarloResult, plan: HouseholdPlan) -> None:
    with st.expander("Market profile, assumptions and warnings"):
        means = ", ".join(f"{key} {value:.2%}" for key, value in result.resolved_arithmetic_means.items())
        st.markdown(
            f"**Return method:** {result.return_method} · **Calibration:** {result.calibration_profile} "
            f"{result.calibration_version}" + (f"  \n**Resolved arithmetic means:** {means}" if means else "")
        )
        render_lines("Material assumptions", plan.material_assumptions())
        render_lines("Defaulted inputs", result.defaulted_inputs)
        render_lines("Warnings", result.warnings)


def render_lines(title: str, lines: list[str]) -> None:
    if lines:
        st.markdown(f"**{title}**\n" + "\n".join(f"- {line}" for line in lines))


def _render_fan_chart(result: MonteCarloResult, plan: HouseholdPlan) -> None:
    """Draw a fan chart of net worth percentile bands from sample paths."""
    has_all_path_percentiles = (
        bool(result.net_worth_percentiles_by_year)
        and bool(result.person1_ages)
        and all(key in result.net_worth_percentiles_by_year for key in _PERCENTILE_KEYS)
    )

    if not has_all_path_percentiles and not result.sample_paths:
        st.info("No paths available for fan chart.")
        return

    person1_name = plan.household.person1.name.split()[0]
    if has_all_path_percentiles:
        ages = result.person1_ages
        p10, p25, p50, p75, p90 = (list(result.net_worth_percentiles_by_year[key]) for key in _PERCENTILE_KEYS)
        years = [[year] for year in result.projection_years]
        dollars = f"{result.valuation_year} dollars"
    else:
        n_years = len(result.sample_paths[0].years)
        if n_years == 0:
            return

        ages = [result.sample_paths[0].years[t].person1_age for t in range(n_years)]

        # Fallback for legacy result objects with only sample paths, which stay nominal.
        nw_arr = np.array([[path.years[t].total_net_worth for t in range(n_years)] for path in result.sample_paths])
        p10, p25, p50, p75, p90 = (np.percentile(nw_arr, key, axis=0).tolist() for key in _PERCENTILE_KEYS)
        years = [[result.sample_paths[0].years[t].year] for t in range(n_years)]
        dollars = "nominal dollars"
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
        title=f"Liquid Net Worth Distribution ({dollars})",
        xaxis_title=f"{person1_name} Age",
        yaxis_title=f"Liquid Net Worth ({dollars})",
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
