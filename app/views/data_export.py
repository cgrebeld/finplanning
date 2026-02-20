"""Data & Export section — year grid and Excel export buttons."""

import tempfile
from pathlib import Path

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.services.export import (
    header_labels_for_plan,
    rows_for_summary_output,
    rows_for_tabular_output,
    write_xlsx,
)
from finplanning_core.services.planning import PlanningService

from app.components.year_grid import render_year_grid
from app.state import get_selected_flow_year


def render_data_export(projection: ProjectionResult, service: PlanningService) -> None:
    """Render the year grid and Excel export download buttons."""
    st.header("Data & Export")
    selected_year = get_selected_flow_year(projection)
    render_year_grid(projection, service.plan, selected_year=selected_year)

    export_summary_col, export_detailed_col = st.columns(2)

    with export_summary_col:
        st.download_button(
            label="Export Summary",
            data=_build_summary_xlsx(projection, service),
            file_name="projection_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with export_detailed_col:
        st.download_button(
            label="Export Detailed",
            data=_build_detailed_xlsx(projection, service),
            file_name="projection_detailed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _build_summary_xlsx(projection: ProjectionResult, service: PlanningService) -> bytes:
    rows = rows_for_summary_output(projection, service.plan)
    labels = {f: f for f in rows[0]}
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        write_xlsx(
            rows,
            tmp_path,
            header_labels=labels,
            chart_x_field="Year",
            chart_series=[("Net Worth", "Net Worth")],
        )
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _build_detailed_xlsx(projection: ProjectionResult, service: PlanningService) -> bytes:
    account_ids = [acc.id for acc in service.plan.accounts]
    rows = rows_for_tabular_output(projection, account_ids)
    labels, series = header_labels_for_plan(list(rows[0].keys()), service.plan)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        write_xlsx(rows, tmp_path, header_labels=labels, chart_series=series)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
