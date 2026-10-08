"""Data & Export section — year grid and Excel export buttons."""

import tempfile
from collections.abc import Callable
from pathlib import Path

import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan
from finplanning_core.services import (
    header_labels_for_plan,
    rows_for_summary_output,
    rows_for_tabular_output,
    write_xlsx,
)

from ..components.year_grid import render_year_grid
from ..state import get_selected_flow_year


def render_data_export(projection: ProjectionResult, plan: HouseholdPlan) -> None:
    """Render the year grid and Excel export download buttons."""
    st.header("Data & Export")
    selected_year = get_selected_flow_year(projection)
    render_year_grid(projection, plan, selected_year=selected_year)

    export_summary_col, export_detailed_col = st.columns(2)

    with export_summary_col:
        st.download_button(
            label="Export Summary",
            data=_cached_xlsx("summary", _build_summary_xlsx, projection, plan),
            file_name="projection_summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with export_detailed_col:
        st.download_button(
            label="Export Detailed",
            data=_cached_xlsx("detailed", _build_detailed_xlsx, projection, plan),
            file_name="projection_detailed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def _cached_xlsx(
    kind: str,
    build: Callable[[ProjectionResult, HouseholdPlan], bytes],
    projection: ProjectionResult,
    plan: HouseholdPlan,
) -> bytes:
    """Build an export once per projection rather than on every rerun of this view."""
    key = f"_xlsx_{kind}"
    cached = st.session_state.get(key)
    if cached is None or cached[0] is not projection:
        cached = (projection, build(projection, plan))
        st.session_state[key] = cached
    return cached[1]


def _build_summary_xlsx(projection: ProjectionResult, plan: HouseholdPlan) -> bytes:
    rows = rows_for_summary_output(projection, plan)
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


def _build_detailed_xlsx(projection: ProjectionResult, plan: HouseholdPlan) -> bytes:
    account_ids = [acc.id for acc in plan.accounts]
    rows = _flatten_rows(rows_for_tabular_output(projection, account_ids))
    labels, series = header_labels_for_plan(list(rows[0].keys()), plan)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        write_xlsx(rows, tmp_path, header_labels=labels, chart_series=series)
        return Path(tmp_path).read_bytes()
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def _cell_value(value: object) -> object:
    value = getattr(value, "value", value)  # enums
    return value if isinstance(value, int | float | str | None) else str(value)


def _flatten_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Expand dict-valued fields into ``<field>_<key>`` columns, since xlsxwriter cannot write dicts.

    ponytail: works around finplanning_core's rows_for_tabular_output leaving per-person/per-account
    dicts unflattened; drop once the engine flattens them itself.
    """
    flat_rows: list[dict[str, object]] = []
    for row in rows:
        flat: dict[str, object] = {}
        for field, value in row.items():
            if isinstance(value, dict):
                for key, sub_value in value.items():
                    flat[f"{field}_{key}"] = _cell_value(sub_value)
            else:
                flat[field] = _cell_value(value)
        flat_rows.append(flat)
    # Dict keys can differ by year (e.g. a person who has died), so use the union of columns.
    fieldnames = list(dict.fromkeys(field for row in flat_rows for field in row))
    return [{field: row.get(field) for field in fieldnames} for row in flat_rows]
