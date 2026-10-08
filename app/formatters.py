"""Pure data transformation from ProjectionResult to pandas DataFrame.

No Streamlit imports — only pandas. This keeps the module testable
without a running Streamlit server.
"""

import pandas as pd
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan
from finplanning_core.services import projection_to_dataframe as _engine_projection_to_dataframe
from pandas.io.formats.style import Styler

MONEY_COLUMNS = [
    "Income",
    "Portfolio Dividends",
    "Portfolio Interest",
    "Realized Cap Gains",
    "Taxable Cap Gains",
    "Expenses",
    "Tax",
    "OAS Clawback",
    "Net Income",
    "Cash Flow",
    "Withdrawals",
    "Non-Reg",
    "RRSP/RRIF",
    "TFSA",
    "Net Worth",
]

INTEGER_COLUMNS = ["Year"]


def projection_to_dataframe(result: ProjectionResult, plan: HouseholdPlan) -> pd.DataFrame:
    """The engine's display DataFrame, plus an OAS Clawback column when any clawback occurs.

    The engine's ``Tax`` column excludes the clawback, which is a separate repayment.
    """
    df = _engine_projection_to_dataframe(result, plan)
    clawback = [yr.oas_clawback for yr in result.years]
    if any(clawback) and "Tax" in df.columns:
        df.insert(df.columns.get_loc("Tax") + 1, "OAS Clawback", clawback)
    return df


def underfunded_purchase_warnings(result: ProjectionResult, plan: HouseholdPlan) -> list[str]:
    """Describe real-asset purchases the plan could not fund (the engine skips them silently)."""
    names = {asset.id: asset.name for asset in plan.real_assets}
    return [
        f"The {names.get(asset_id, asset_id)} purchase planned for {yr.year} could not be fully funded, "
        "so the projection does not include it."
        for yr in result.years
        for asset_id, underfunded in yr.real_asset_purchase_underfunded.items()
        if underfunded
    ]


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
