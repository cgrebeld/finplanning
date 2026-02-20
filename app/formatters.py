"""Pure data transformation from ProjectionResult to pandas DataFrame.

No Streamlit imports — only pandas. This keeps the module testable
without a running Streamlit server.
"""

import pandas as pd
from finplanning_core.services.export import projection_to_dataframe as projection_to_dataframe
from pandas.io.formats.style import Styler

MONEY_COLUMNS = [
    "Income",
    "Portfolio Dividends",
    "Portfolio Interest",
    "Realized Cap Gains",
    "Taxable Cap Gains",
    "Expenses",
    "Tax",
    "Net Income",
    "Cash Flow",
    "Withdrawals",
    "Non-Reg",
    "RRSP/RRIF",
    "TFSA",
    "Net Worth",
]

INTEGER_COLUMNS = ["Year"]


def _style_negative_red(val: object) -> str:
    """Return CSS for negative numeric values."""
    if isinstance(val, int | float) and val < 0:
        return "color: red; font-weight: bold"
    return ""


def style_cash_flow(df: pd.DataFrame) -> Styler:
    """Apply conditional formatting to the projection DataFrame.

    - Red + bold on negative Cash Flow values
    - Currency format on money columns
    - Integer format on Year / Age columns
    """
    money_cols = [c for c in MONEY_COLUMNS if c in df.columns]
    age_cols = [c for c in df.columns if c.endswith(" Age")]
    int_cols = [c for c in INTEGER_COLUMNS if c in df.columns]

    format_map: dict[str, str] = {}
    for col in money_cols:
        format_map[col] = "${:,.0f}"
    for col in int_cols + age_cols:
        format_map[col] = "{:.0f}"

    styler = df.style.format(format_map)
    if "Cash Flow" in df.columns:
        styler = styler.map(_style_negative_red, subset=["Cash Flow"])
    return styler
