"""Year-by-year projection grid component."""

from __future__ import annotations

from typing import Any

import streamlit as st
from finplanning_core.engine.projection import ProjectionResult
from finplanning_core.models.plan import HouseholdPlan

from app.formatters import projection_to_dataframe, style_cash_flow


def _style_selected_year_row(styled: Any, selected_year: int | None) -> Any:
    if selected_year is None:
        return styled

    def _row_style(row: Any) -> list[str]:
        year_value = row.get("Year") if hasattr(row, "get") else None
        if year_value is not None and int(year_value) == selected_year:
            return ["border: 2px solid #ff4da6"] * len(row)
        return [""] * len(row)

    if hasattr(styled, "apply"):
        return styled.apply(_row_style, axis=1)
    return styled


def render_year_grid(projection: ProjectionResult, plan: HouseholdPlan, selected_year: int | None = None) -> None:
    """Render the styled year-by-year projection grid."""
    st.subheader(
        "Year-by-Year Projection",
        help="Tabular breakdown of each projection year showing income, expenses, taxes, net income, "
        "cash flow gaps, withdrawals, account balances, and total net worth. The selected year "
        "is highlighted with a pink border. Negative cash flow values appear in red.",
    )
    df = projection_to_dataframe(projection, plan)
    styled = style_cash_flow(df)
    styled = _style_selected_year_row(styled, selected_year)
    height = min(len(df) * 35 + 50, 800)
    st.dataframe(
        styled,
        width="container",
        hide_index=True,
        height=height,
    )
