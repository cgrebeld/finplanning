"""Cash flow Sankey chart for tracing yearly inflows to outflows."""

from __future__ import annotations

from collections import defaultdict

import plotly.graph_objects as go
import streamlit as st
from finplanning_core.engine.inflation import inflate
from finplanning_core.engine.projection import ProjectionResult, YearlyProjection
from finplanning_core.models.accounts import AccountType
from finplanning_core.models.plan import HouseholdPlan
from finplanning_core.tax.calculator import TaxCalculator

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
    "Balance Adjustment",
]

DESTINATION_ORDER = [
    "Income Tax",
    "Capital Gains Tax",
    "Expenses",
    "RRSP/RRIF Contributions",
    "TFSA Contributions",
    "Non-Registered Contributions",
    "Other Contributions",
    "Portfolio Reinvestment",
    "Unallocated Cash",
]

MIN_DISPLAY_FLOW = 5.0


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


def _group_positive_net_deposits_by_account_type(yearly: YearlyProjection, plan: HouseholdPlan) -> dict[str, float]:
    account_type_by_id = {account.id: account.account_type for account in plan.accounts}
    grouped: defaultdict[str, float] = defaultdict(float)

    for account_id, net_deposit in yearly.account_net_deposits.items():
        if net_deposit <= 0:
            continue
        account_type = account_type_by_id.get(account_id)
        if account_type in {AccountType.RRSP, AccountType.RRIF, AccountType.LIRA, AccountType.LIF}:
            grouped["RRSP/RRIF Contributions"] += net_deposit
        elif account_type == AccountType.TFSA:
            grouped["TFSA Contributions"] += net_deposit
        elif account_type == AccountType.NON_REGISTERED:
            grouped["Non-Registered Contributions"] += net_deposit
        else:
            grouped["Other Contributions"] += net_deposit

    return dict(grouped)


def _event_expense_destinations(
    yearly: YearlyProjection, plan: HouseholdPlan, projection_start_year: int
) -> dict[str, float]:
    destinations: dict[str, float] = {}

    for event in plan.one_time_events:
        if event.event_type == "expense" and event.applies_to_year(yearly.year):
            label = f"One-Time: {event.name}"
            destinations[label] = destinations.get(label, 0.0) + event.amount

    for recurring in plan.recurring_expenses:
        if yearly.year < recurring.start_year:
            continue
        if recurring.end_year is not None and yearly.year > recurring.end_year:
            continue
        if (yearly.year - recurring.start_year) % recurring.period_years != 0:
            continue
        years_elapsed = yearly.year - projection_start_year
        amount = inflate(recurring.amount, plan.assumptions.inflation.general, years_elapsed)
        label = f"Recurring: {recurring.name}"
        destinations[label] = destinations.get(label, 0.0) + amount

    return destinations


def _split_tax_destinations(yearly: YearlyProjection, plan: HouseholdPlan) -> dict[str, float]:
    total_tax = yearly.total_tax
    taxable_capital_gains = yearly.taxable_capital_gains
    if total_tax <= 0:
        return {}

    if taxable_capital_gains <= 0:
        return {"Income Tax": total_tax}

    base_taxable_income = max(yearly.total_income + yearly.withdrawal_rrsp_rrif, 0.0)
    full_taxable_income = base_taxable_income + taxable_capital_gains
    province = plan.household.province.value
    projection_assumptions = plan.assumptions.tax_projection.model_dump(mode="python")
    calculator = TaxCalculator(projection_assumptions=projection_assumptions)

    base_tax = calculator.calculate_tax(
        taxable_income=base_taxable_income,
        tax_year=yearly.year,
        province=province,
    ).total_tax
    full_tax = calculator.calculate_tax(
        taxable_income=full_taxable_income,
        tax_year=yearly.year,
        province=province,
    ).total_tax
    capital_gains_tax = max(full_tax - base_tax, 0.0)
    capital_gains_tax = min(capital_gains_tax, total_tax)
    income_tax = total_tax - capital_gains_tax
    return {
        "Income Tax": income_tax,
        "Capital Gains Tax": capital_gains_tax,
    }


def build_cash_flow_sankey_figure(
    projection: ProjectionResult, plan: HouseholdPlan, selected_year: int, zoom_scale: float = 1.0
) -> go.Figure:
    """Build Sankey figure for a selected projection year."""
    yearly = _find_yearly_projection(projection, selected_year)

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
    }
    source_amounts = {name: value for name, value in source_amounts.items() if _meets_display_threshold(value)}

    destination_amounts: dict[str, float] = _split_tax_destinations(yearly, plan)
    event_expense_destinations = _event_expense_destinations(yearly, plan, projection.years[0].year)
    regular_expenses = yearly.total_expenses - sum(event_expense_destinations.values(), 0.0)
    destination_amounts["Expenses"] = max(regular_expenses, 0.0)
    destination_amounts.update(event_expense_destinations)
    destination_amounts.update(_group_positive_net_deposits_by_account_type(yearly, plan))
    destination_amounts = {
        name: value for name, value in destination_amounts.items() if _meets_display_threshold(value)
    }

    source_total = sum(source_amounts.values(), 0.0)
    destination_total = sum(destination_amounts.values(), 0.0)
    if source_total > destination_total:
        gap = source_total - destination_total
        if _meets_display_threshold(gap):
            reinvestable_income = yearly.portfolio_dividend_income + yearly.portfolio_interest_income
            reinvestment = min(gap, reinvestable_income)
            if _meets_display_threshold(reinvestment):
                destination_amounts["Portfolio Reinvestment"] = reinvestment
                gap -= reinvestment
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

    node_colors = []
    node_x: list[float] = []
    for label in labels:
        if label == hub_label:
            node_colors.append("lightslategray")
            node_x.append(0.5)
        elif label in {"Income Tax", "Capital Gains Tax"}:
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
                    "hovertemplate": "%{label}<br>Total: $%{value:,.0f}<extra></extra>",
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
                    "color": [c.replace(")", ", 0.25)").replace("rgb", "rgba") if "rgb" in c else c for c in link_colors],
                    "hovertemplate": (
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
        help="Sankey diagram tracing all income sources on the left through to expenses, taxes, "
        "contributions, and reinvestment on the right for the selected year. Flow widths are "
        "proportional to dollar amounts. Use the year slider to explore different years.",
    )
    fig = build_cash_flow_sankey_figure(projection, plan, selected_year, zoom_scale=zoom_scale)
    st.plotly_chart(fig, width="container")
