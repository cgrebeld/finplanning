"""Data & Export section — year grid, Excel exports and a JSON results export."""

import json
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import streamlit as st
from finplanning_core.engine import EstateCalculationStatus, ProjectionResult, calculate_projection_estate
from finplanning_core.models import HouseholdPlan
from finplanning_core.risk import MonteCarloResult
from finplanning_core.services import (
    header_labels_for_plan,
    rows_for_summary_output,
    rows_for_tabular_output,
    write_xlsx,
)

from ..charts.gap_analysis import capacity_note
from ..components.year_grid import render_year_grid
from ..state import get_selected_flow_year
from .monte_carlo import mc_summary

_YEARLY_FIELDS = (
    "total_income",
    "total_tax",
    "total_expenses",
    "total_withdrawals",
    "total_net_worth",
    "total_real_asset_value",
    "total_household_asset_value",
    "cash_flow_gap",
    "real_asset_sale_proceeds",
    "real_asset_selling_costs",
    "real_asset_purchase_costs",
    "real_asset_net_cashflow",
)


def render_data_export(projection: ProjectionResult, plan: HouseholdPlan) -> None:
    """Render the year grid and Excel export download buttons."""
    st.header("Data & Export")
    selected_year = get_selected_flow_year(projection)
    render_year_grid(projection, plan, selected_year=selected_year)

    export_summary_col, export_detailed_col, export_json_col = st.columns(3)

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

    with export_json_col:
        mc_result: MonteCarloResult | None = st.session_state.get("mc_result")
        if mc_result is not None and mc_result.scenario_id != projection.scenario_id:
            mc_result = None
        st.download_button(
            label="Export Results (JSON)",
            data=json.dumps(results_summary(projection, plan, mc_result), indent=2),
            file_name="projection_results.json",
            mime="application/json",
            help="Headline metrics with their dollar basis and horizons, the yearly summary, the estate and "
            "the latest Monte Carlo run for this scenario.",
        )


def _money(value: float) -> float:
    return round(value, 2)


def results_summary(
    projection: ProjectionResult, plan: HouseholdPlan, mc_result: MonteCarloResult | None = None
) -> dict[str, Any]:
    """Results with explicit units, mirroring the engine's run_projection/run_monte_carlo tool JSON keys."""
    years = projection.years
    metrics = {
        "scenario_id": projection.scenario_id,
        "final_net_worth": _money(projection.final_net_worth),
        "final_real_asset_value": _money(projection.final_real_asset_value),
        "final_total_household_asset_value": _money(projection.final_total_household_asset_value),
        "depletion_age": projection.depletion_age,
        "sustainable_spending": _money(projection.sustainable_spending),
        "desired_spending": _money(projection.desired_spending),
        "spending_gap": _money(projection.spending_gap),
        "sustainable_spending_status": projection.sustainable_spending_status,
        "terminal_reserve_years": projection.terminal_reserve_years,
        "spending_method": projection.spending_method,
        "valuation_year": projection.valuation_year,
        "defaulted_inputs": list(projection.defaulted_inputs),
        "material_assumptions": plan.material_assumptions(),
        "warnings": list(projection.warnings),
    }
    yearly = [
        {
            "year": yr.year,
            "person1_age": yr.person1_age,
            "person2_age": yr.person2_age,
            "marginal_tax_rate": yr.marginal_tax_rate,
            **{field: _money(getattr(yr, field)) for field in _YEARLY_FIELDS},
        }
        for yr in years
    ]
    return {
        "units": {
            "projection": "Nominal dollars. final_net_worth and total_net_worth are liquid investment accounts; "
            "household values add the gross value of real assets.",
            "spending": f"Deterministic first-year amounts in {projection.valuation_year} dollars.",
            "estate": "Nominal at the last death; after_tax_real is in valuation_year dollars.",
            "monte_carlo": "percentiles are final liquid net worth in valuation_year dollars at reporting_end_year; "
            "depletion and estate outcomes run through risk_end_year; estate-cost percentiles are nominal.",
        },
        "start_year": years[0].year if years else None,
        "reporting_end_year": years[-1].year if years else None,
        "metrics": metrics,
        "sustainable_spending_note": capacity_note(projection),
        "yearly_summary": yearly,
        "estate": _estate_summary(projection, plan),
        "monte_carlo": mc_summary(mc_result) if mc_result is not None else None,
    }


def _estate_summary(projection: ProjectionResult, plan: HouseholdPlan) -> dict[str, Any]:
    try:
        estate = calculate_projection_estate(plan, projection)
    except Exception as exc:  # noqa: BLE001 - reported in the export, like the overview does
        return {"status": "ERROR", "error": str(exc)}
    if estate.status != EstateCalculationStatus.CALCULATED:
        return {"status": str(estate.status.value), "unsupported_reasons": list(estate.unsupported_reasons)}
    return {
        "status": str(estate.status.value),
        "death_year": estate.death_year,
        "valuation_year": estate.valuation_year,
        "gross_estate": _money(estate.gross_estate),
        "terminal_total_tax": _money(estate.terminal_total_tax),
        "total_estate_costs": _money(estate.total_estate_costs),
        "after_tax_nominal": _money(estate.after_tax_nominal),
        "after_tax_real": _money(estate.after_tax_real),
    }


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
    for row, yr in zip(rows, projection.years, strict=True):
        row["Real Assets"] = yr.total_real_asset_value
        row["Household Assets"] = yr.total_household_asset_value
    labels = {f: f if f == "Year" or f.endswith(" Age") else f"{f} (nominal $)" for f in rows[0]}
    labels["Net Worth"] = "Liquid Net Worth (nominal $)"
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        write_xlsx(
            rows,
            tmp_path,
            header_labels=labels,
            chart_x_field="Year",
            chart_series=[("Net Worth", "Liquid Net Worth"), ("Household Assets", "Household Assets")],
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
