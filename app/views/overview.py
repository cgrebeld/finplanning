"""Overview section — summary metrics and gap chart."""

import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.services import PlanningService

from ..charts.gap_analysis import render_gap_chart
from ..components.summary_metrics import render_summary_metrics


def render_overview(projection: ProjectionResult, service: PlanningService) -> None:
    """Render the overview section with summary metrics and gap analysis chart."""
    st.header(f"Overview: {service.plan.household.name}")
    render_summary_metrics(projection)
    st.divider()
    render_gap_chart(projection.desired_spending, projection.sustainable_spending)
