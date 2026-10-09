"""Cash flow Sankey chart for tracing yearly inflows to outflows."""

import plotly.graph_objects as go
import streamlit as st
from finplanning_core.engine import ProjectionResult, YearlyProjection
from finplanning_core.models import AccountType, HouseholdPlan

SOURCE_ORDER = [
    "Employment Income",
    "Pension Income",
    "CPP Income",
    "OAS Income",
    "Portfolio Dividend Income",
    "Portfolio Interest Income",
    "Investment Income",
    "Other Income",
    "One-Time Income",
    "Non-Reg Withdrawals",
    "RRSP/RRIF Withdrawals",
    "TFSA Withdrawals",
    "Estate Settlement Draw",
    "Real Asset Sale",
    "Cash Savings Draw",
    "Unfunded Shortfall",
    "Balance Adjustment",
]

DESTINATION_ORDER = [
    "Income Tax",
    "Capital Gains Tax",
    "Estate Settlement Tax",
    "OAS Clawback",
    "Payroll Deductions",
    "Estate Costs",
    "Expenses",
    "Real Asset Purchase",
    "Real Asset Selling Costs",
    "RRSP/RRIF Contributions",
    "TFSA Contributions",
    "Non-Registered Contributions",
    "Cash Savings",
    "Unallocated Cash",
]

_REGISTERED_TYPES = {AccountType.RRSP, AccountType.RRIF, AccountType.LIRA, AccountType.LIF}

MIN_DISPLAY_FLOW = 5.0

# RGB for the named node colours, used to draw translucent links.
_LINK_RGB = {
    "mediumseagreen": "60, 179, 113",
    "red": "255, 0, 0",
    "cornflowerblue": "100, 149, 237",
}


def _recommended_sankey_height(source_count: int, destination_count: int) -> int:
    """Scale chart height to active node count so nodes and links do not clip."""
    max_side = max(source_count, destination_count)
    raw_height = 240 + (max_side * 72)
    return max(500, min(920, raw_height))


def _meets_display_threshold(amount: float) -> bool:
    return amount >= MIN_DISPLAY_FLOW


def _find_yearly_projection(projection: ProjectionResult, selected_year: int) -> YearlyProjection:
    yearly = next((year for year in projection.years if year.year == selected_year), None)
    if yearly is None:
        raise ValueError(f"Selected year {selected_year} not found in projection.")
    return yearly


def _account_group(account_type: AccountType | None) -> str:
    if account_type in _REGISTERED_TYPES:
        return "RRSP/RRIF"
    if account_type == AccountType.TFSA:
        return "TFSA"
    return "Non-Registered"


def _gross_deposits_by_group(yearly: YearlyProjection, plan: HouseholdPlan) -> dict[str, float]:
    """Gross money deposited into each account group this year.

    ``account_net_deposits`` is net of withdrawals, estate draws and the non-registered distributions
    paid out as cash, so add those back: gross deposits = net deposits + withdrawals + estate
    settlement outflows (+ distributions for non-registered accounts).
    """
    account_types = {account.id: account.account_type for account in plan.accounts} | dict(yearly.account_types)
    gross = {
        "RRSP/RRIF": yearly.withdrawal_rrsp_rrif,
        "TFSA": yearly.withdrawal_tfsa,
        "Non-Registered": yearly.withdrawal_non_reg
        + yearly.portfolio_dividend_income
        + yearly.portfolio_interest_income,
    }
    for per_account in (yearly.account_net_deposits, yearly.account_estate_settlement_outflows):
        for account_id, amount in per_account.items():
            gross[_account_group(account_types.get(account_id))] += amount
    return {f"{group} Contributions": max(amount, 0.0) for group, amount in gross.items()}


def _event_expense_destinations(yearly: YearlyProjection, plan: HouseholdPlan) -> dict[str, float]:
    """Name the engine's per-item one-time and recurring expense amounts."""
    destinations: dict[str, float] = {}
    for prefix, items, amounts in (
        ("One-Time", plan.one_time_events, yearly.one_time_expense_amounts),
        ("Recurring", plan.recurring_expenses, yearly.recurring_expense_amounts),
    ):
        names = {item.id: item.name for item in items}
        for item_id, amount in amounts.items():
            label = f"{prefix}: {names.get(item_id, item_id)}"
            destinations[label] = destinations.get(label, 0.0) + amount
    return destinations


def _regular_expense_components(yearly: YearlyProjection, plan: HouseholdPlan) -> dict[str, float]:
    """Label the engine's components of the "Expenses" node: plan expense items, real-asset
    carrying costs and any spending adjustment."""
    expense_names = {expense.id: expense.name for expense in plan.expenses}
    asset_names = {asset.id: asset.name for asset in plan.real_assets}
    components: dict[str, float] = {}
    for expense_id, amount in yearly.expense_amounts.items():
        name = expense_names.get(expense_id, expense_id)
        components[name] = components.get(name, 0.0) + amount
    for asset_id, amount in yearly.real_asset_carrying_costs_by_asset.items():
        components[f"{asset_names.get(asset_id, asset_id)} Carrying Costs"] = amount
    components["Spending Adjustment"] = yearly.expense_delta
    return {name: amount for name, amount in components.items() if abs(amount) >= MIN_DISPLAY_FLOW}


def _split_tax_destinations(yearly: YearlyProjection) -> dict[str, float]:
    """Split total tax into income tax and the engine's incremental tax on taxable capital gains."""
    destinations = {"Estate Settlement Tax": yearly.estate_settlement_tax}
    total_tax = yearly.total_tax - yearly.estate_settlement_tax  # total_tax includes it
    if total_tax <= 0:
        return destinations
    capital_gains_tax = min(sum(yearly.capital_gains_tax_by_person.values(), 0.0), total_tax)
    return {
        **destinations,
        "Income Tax": total_tax - capital_gains_tax,
        "Capital Gains Tax": capital_gains_tax,
    }


def build_cash_flow_sankey_figure(
    projection: ProjectionResult, plan: HouseholdPlan, selected_year: int, zoom_scale: float = 1.0
) -> go.Figure:
    """Build Sankey figure for a selected projection year."""
    yearly = _find_yearly_projection(projection, selected_year)
    prior = next((y for y in projection.years if y.year == selected_year - 1), None)
    # Surplus the engine holds outside the accounts (e.g. beyond contribution room).
    cash_change = yearly.external_cash_balance - (prior.external_cash_balance if prior is not None else 0.0)
    person1_name = plan.household.person1.name.split()[0]
    year_context = f"{person1_name} is {yearly.person1_age}: {selected_year} (nominal dollars)"

    source_amounts: dict[str, float] = {
        "Employment Income": yearly.employment_income,
        "Pension Income": yearly.pension_income,
        "CPP Income": yearly.cpp_income,
        "OAS Income": yearly.oas_income,
        "Portfolio Dividend Income": yearly.portfolio_dividend_income,
        "Portfolio Interest Income": yearly.portfolio_interest_income,
        "Investment Income": yearly.investment_income,
        "Other Income": yearly.other_income,
        "One-Time Income": yearly.one_time_income,
        "Non-Reg Withdrawals": yearly.withdrawal_non_reg,
        "RRSP/RRIF Withdrawals": yearly.withdrawal_rrsp_rrif,
        "TFSA Withdrawals": yearly.withdrawal_tfsa,
        "Estate Settlement Draw": sum(yearly.account_estate_settlement_outflows.values(), 0.0),
        "Real Asset Sale": yearly.real_asset_sale_proceeds,
        "Cash Savings Draw": max(-cash_change, 0.0),
        # Spending the plan could not fund: the only legitimate balancing source.
        "Unfunded Shortfall": max(-yearly.cash_flow_gap, 0.0),
    }
    source_amounts = {name: value for name, value in source_amounts.items() if _meets_display_threshold(value)}

    destination_amounts: dict[str, float] = _split_tax_destinations(yearly)
    event_expense_destinations = _event_expense_destinations(yearly, plan)
    regular_expenses = yearly.total_expenses - yearly.one_time_expense - yearly.recurring_expense
    destination_amounts["Expenses"] = max(regular_expenses, 0.0)
    expense_components = _regular_expense_components(yearly, plan)
    destination_amounts.update(event_expense_destinations)
    destination_amounts["OAS Clawback"] = yearly.oas_clawback
    destination_amounts["Payroll Deductions"] = yearly.payroll_deductions
    destination_amounts["Estate Costs"] = yearly.estate_total_costs
    destination_amounts["Real Asset Purchase"] = (
        sum(yearly.real_asset_purchase_prices.values(), 0.0) + yearly.real_asset_purchase_costs
    )
    destination_amounts["Real Asset Selling Costs"] = yearly.real_asset_selling_costs
    destination_amounts.update(_gross_deposits_by_group(yearly, plan))
    destination_amounts["Cash Savings"] = max(cash_change, 0.0)
    destination_amounts = {
        name: value for name, value in destination_amounts.items() if _meets_display_threshold(value)
    }

    # The flows above follow the engine's cash identity and balance exactly; these plugs only
    # appear if the engine's accounting changes.
    source_total = sum(source_amounts.values(), 0.0)
    destination_total = sum(destination_amounts.values(), 0.0)
    if source_total > destination_total:
        gap = source_total - destination_total
        if _meets_display_threshold(gap):
            destination_amounts["Unallocated Cash"] = gap
    elif destination_total > source_total:
        gap = destination_total - source_total
        if _meets_display_threshold(gap):
            source_amounts["Balance Adjustment"] = gap

    source_labels = [label for label in SOURCE_ORDER if label in source_amounts]
    destination_labels = [label for label in DESTINATION_ORDER if label in destination_amounts]
    dynamic_destinations = sorted(
        label
        for label in destination_amounts
        if label not in DESTINATION_ORDER and (label.startswith("One-Time: ") or label.startswith("Recurring: "))
    )
    destination_labels.extend(dynamic_destinations)
    hub_label = "Available Cash"
    labels = source_labels + [hub_label] + destination_labels

    hub_index = len(source_labels)
    label_to_index = {label: idx for idx, label in enumerate(labels)}

    link_sources: list[int] = []
    link_targets: list[int] = []
    link_values: list[float] = []

    for label, amount in source_amounts.items():
        link_sources.append(label_to_index[label])
        link_targets.append(hub_index)
        link_values.append(amount)

    for label, amount in destination_amounts.items():
        link_sources.append(hub_index)
        link_targets.append(label_to_index[label])
        link_values.append(amount)

    node_details = [""] * len(labels)
    if "Expenses" in label_to_index and expense_components:
        node_details[label_to_index["Expenses"]] = "".join(
            f"<br>• {name}: ${amount:,.0f}"
            for name, amount in sorted(expense_components.items(), key=lambda item: -item[1])
        )

    node_colors = []
    node_x: list[float] = []
    for label in labels:
        if label == hub_label:
            node_colors.append("lightslategray")
            node_x.append(0.5)
        elif label in {"Income Tax", "Capital Gains Tax", "Estate Settlement Tax", "OAS Clawback"}:
            node_colors.append("red")
            node_x.append(0.99)
        elif label in source_amounts:
            node_colors.append("mediumseagreen")
            node_x.append(0.01)
        else:
            node_colors.append("cornflowerblue")
            node_x.append(0.99)

    hover_font = {"size": 14, "color": "white", "family": "Arial, sans-serif"}
    link_colors = []
    for src_idx in link_sources:
        base = node_colors[src_idx]
        link_colors.append(base if base != "lightslategray" else "cornflowerblue")

    fig = go.Figure(
        data=[
            go.Sankey(
                arrangement="snap",
                node={
                    "label": labels,
                    "pad": 24,
                    "thickness": 14,
                    "color": node_colors,
                    "x": node_x,
                    "customdata": node_details,
                    "hovertemplate": (
                        f"{year_context}<br>%{{label}}<br>Total: $%{{value:,.0f}}%{{customdata}}<extra></extra>"
                    ),
                    "hoverlabel": {
                        "bgcolor": "rgba(50,50,50,0.95)",
                        "bordercolor": "rgba(50,50,50,0.95)",
                        "font": hover_font,
                    },
                },
                textfont={"size": 14, "color": "black"},
                link={
                    "source": link_sources,
                    "target": link_targets,
                    "value": link_values,
                    "color": [f"rgba({_LINK_RGB[c]}, 0.25)" for c in link_colors],
                    "hovertemplate": (
                        f"{year_context}<br>"
                        "%{source.label} → %{target.label}"
                        "<br><b>$%{value:,.0f}</b>"
                        "<extra></extra>"
                    ),
                    "hoverlabel": {
                        "bgcolor": link_colors,
                        "bordercolor": link_colors,
                        "font": hover_font,
                    },
                },
            )
        ]
    )

    scaled_height = int(_recommended_sankey_height(len(source_labels), len(destination_labels)) * zoom_scale)
    fig.update_layout(
        height=max(500, min(1400, scaled_height)),
        margin={"t": 50, "b": 48, "l": 10, "r": 10},
    )
    return fig


def render_cash_flow_sankey(
    projection: ProjectionResult, plan: HouseholdPlan, selected_year: int, zoom_scale: float = 1.0
) -> None:
    """Render the yearly cash-flow Sankey diagram."""
    st.subheader(
        "Cash Flow",
        help="Sankey diagram tracing income, withdrawals, real-asset sales and estate draws on the left "
        "through to taxes, OAS clawback, expenses, real-asset purchases, estate costs and account "
        "deposits (including reinvested income) on the right for the selected year. Flow widths are "
        "proportional to dollar amounts; 'Unfunded Shortfall' is spending the plan could not cover. "
        "Use the year slider to explore different years.",
    )
    fig = build_cash_flow_sankey_figure(projection, plan, selected_year, zoom_scale=zoom_scale)
    st.plotly_chart(fig, width="stretch")
