"""Year-by-year projection grid component."""

import pandas as pd
import streamlit as st
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan
from pandas.io.formats.style import Styler

from ..formatters import projection_to_dataframe, style_cash_flow
from ..state import select_year


def _style_selected_year_row(styled: Styler, selected_year: int | None) -> Styler:
    if selected_year is None:
        return styled

    def _row_style(row: pd.Series) -> list[str]:
        year_value = row.get("Year") if hasattr(row, "get") else None
        if year_value is not None and int(year_value) == selected_year:
            return ["border: 2px solid #ff4da6"] * len(row)
        return [""] * len(row)

    return styled.apply(_row_style, axis=1)


def render_year_grid(projection: ProjectionResult, plan: HouseholdPlan, selected_year: int | None = None) -> None:
    """Render the styled year-by-year projection grid."""
    st.subheader(
        "Year-by-Year Projection",
        help="Tabular breakdown of each projection year showing income, expenses, taxes, net income, "
        "cash flow gaps, withdrawals, account balances, and total net worth. The selected year "
        "is highlighted with a pink border; click a row to select a different year. Negative cash "
        "flow values appear in red.",
    )
    df = projection_to_dataframe(projection, plan)
    styled = style_cash_flow(df)
    styled = _style_selected_year_row(styled, selected_year)
    height = min(len(df) * 35 + 50, 800)
    event = st.dataframe(
        styled,
        width="stretch",
        hide_index=True,
        height=height,
        key="year_grid",
        on_select="rerun",
        selection_mode="single-row",
    )
    rows = event.selection.rows
    select_year(int(df.iloc[rows[0]]["Year"]) if rows else None)
