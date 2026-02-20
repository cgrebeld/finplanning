"""Cash Flow section — year slider and Sankey diagram."""

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.services.planning import PlanningService

from app.charts.cash_flow_sankey import render_cash_flow_sankey
from app.state import get_selected_flow_year, set_selected_flow_year


def render_cash_flow(projection: ProjectionResult, service: PlanningService) -> None:
    """Render the year selector slider and cash flow Sankey diagram."""
    st.header("Cash Flow")

    selected_flow_year = get_selected_flow_year(projection)
    years = [year.year for year in projection.years]
    slider_key = "selected_flow_year_slider"
    st.session_state[slider_key] = selected_flow_year

    def _on_selected_year_slider_change() -> None:
        slider_year_value = st.session_state.get(slider_key)
        if isinstance(slider_year_value, int):
            set_selected_flow_year(slider_year_value)

    sankey_col1, _ = st.columns([2, 1])
    with sankey_col1:
        slider_year = st.slider(
            "Select Year",
            min_value=min(years),
            max_value=max(years),
            step=1,
            key=slider_key,
            on_change=_on_selected_year_slider_change,
            help="Use this slider to choose the year shown in the cash flow diagram.",
        )
    selected_flow_year = int(slider_year)

    render_cash_flow_sankey(projection, service.plan, selected_flow_year, zoom_scale=1.0)
