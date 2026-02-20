"""Net Worth section — net worth chart."""

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.services.planning import PlanningService

from app.charts.net_worth import render_net_worth_chart
from app.state import get_selected_flow_year


def render_net_worth(projection: ProjectionResult, service: PlanningService) -> None:
    """Render the net worth chart for the selected flow year."""
    st.header("Net Worth")
    selected_year = get_selected_flow_year(projection)
    render_net_worth_chart(projection, service.plan, selected_year=selected_year)
