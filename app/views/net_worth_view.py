"""Net Worth section — net worth chart."""

import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan

from ..charts.net_worth import render_net_worth_chart
from ..state import get_selected_flow_year


def render_net_worth(projection: ProjectionResult, plan: HouseholdPlan) -> None:
    """Render the net worth chart for the selected flow year."""
    st.header("Net Worth")
    selected_year = get_selected_flow_year(projection)
    render_net_worth_chart(projection, plan, selected_year=selected_year)
