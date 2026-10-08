"""Tax Analysis section — tax heatmap."""

import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan

from ..charts.tax_heatmap import render_tax_heatmap
from ..state import get_selected_flow_year


def render_tax_analysis(projection: ProjectionResult, plan: HouseholdPlan) -> None:
    """Render the tax heatmap for the selected flow year."""
    st.header("Tax Analysis")
    selected_year = get_selected_flow_year(projection)
    render_tax_heatmap(projection, plan, selected_year=selected_year)
