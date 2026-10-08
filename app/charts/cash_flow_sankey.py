"""Cash flow Sankey chart for tracing yearly inflows to outflows."""


import plotly.graph_objects as go
import streamlit as st
from finplanning_core.engine import inflate
from finplanning_core.engine import ProjectionResult, YearlyProjection
from finplanning_core.models import AccountType
from finplanning_core.models import HouseholdPlan
from finplanning_core.tax import TaxCalculator

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
    "Unfunded Shortfall",
    "Balance Adjustment",
]

DESTINATION_ORDER = [
    "Income Tax",
    "Capital Gains Tax",
    "Estate Settlement Tax",
    "OAS Clawback",
    "Estate Costs",
    "Expenses",
    "Real Asset Purchase",
    "Real Asset Selling Costs",
    "RRSP/RRIF Contributions",
    "TFSA Contributions",
    "Non-Registered Contributions",
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

    ``account_net_deposits`` is net of withdrawals and estate draws from the same accounts, so add
    those back: gross deposits = net deposits + withdrawals + estate settlement outflows.
    """
    account_types = {account.id: account.account_type for account in plan.accounts} | dict(yearly.account_types)
    gross = {
        "RRSP/RRIF": yearly.withdrawal_rrsp_rrif,
        "TFSA": yearly.withdrawal_tfsa,
        "Non-Registered": yearly.withdrawal_non_reg,
    }
    for per_account in (yearly.account_net_deposits, yearly.account_estate_settlement_outflows):
        for account_id, amount in per_account.items():
            gross[_account_group(account_types.get(account_id))] += amount
    return {f"{group} Contributions": max(amount, 0.0) for group, amount in gross.items()}


def _scale_to_total(amounts: dict[str, float], total: float, fallback_label: str) -> dict[str, float]:
    """Keep the plan's per-item labels but make them sum to the engine's total for the year."""
    if total <= 0:
        return {}
    estimate = sum(amounts.values(), 0.0)
    if estimate <= 0:
        return {fallback_label: total}
    return {label: amount * total / estimate for label, amount in amounts.items()}


def _event_expense_destinations(
    yearly: YearlyProjection, plan: HouseholdPlan, projection_start_year: int
) -> dict[str, float]:
    """Name one-time and recurring expenses, sized by the engine's yearly totals.

    The plan supplies which items occur this year and their relative sizes; the engine's
    ``one_time_expense`` / ``recurring_expense`` remain the source of truth for the amounts.
    """
    one_time: dict[str, float] = {}
    for event in plan.one_time_events:
        if event.event_type == "expense" and event.applies_to_year(yearly.year):
            label = f"One-Time: {event.name}"
            one_time[label] = one_time.get(label, 0.0) + event.amount

    recurring: dict[str, float] = {}
    for item in plan.recurring_expenses:
        if yearly.year < item.start_year:
            continue
        if item.end_year is not None and yearly.year > item.end_year:
            continue
        if (yearly.year - item.start_year) % item.period_years != 0:
            continue
        years_elapsed = yearly.year - projection_start_year
        label = f"Recurring: {item.name}"
        recurring[label] = recurring.get(label, 0.0) + inflate(
            item.amount, plan.assumptions.inflation.general, years_elapsed
        )

    return {
        **_scale_to_total(one_time, yearly.one_time_expense, "One-Time: Other"),
        **_scale_to_total(recurring, yearly.recurring_expense, "Recurring: Other"),
    }


def _split_tax_destinations(yearly: YearlyProjection, plan: HouseholdPlan) -> dict[str, float]:
    """Split total tax into income tax and the incremental tax on taxable capital gains.

    The engine taxes each person separately, so the gains' share is computed per person
    as tax(taxable income) - tax(taxable income without that person's gains).
    """
    destinations = {"Estate Settlement Tax": yearly.estate_settlement_tax}
    total_tax = yearly.total_tax - yearly.estate_settlement_tax  # total_tax includes it
    if total_tax <= 0:
        return destinations

    if yearly.taxable_capital_gains <= 0:
        return {**destinations, "Income Tax": total_tax}

    province = plan.household.province.value
    projection_assumptions = plan.assumptions.tax_projection.model_dump(mode="python")
    calculator = TaxCalculator(projection_assumptions=projection_assumptions)

    capital_gains_tax = 0.0
    for person in plan.persons:
        gains = yearly.taxable_capital_gains_by_person.get(person.id, 0.0)
        if gains <= 0:
            continue
        taxable_income = yearly.taxable_income_by_person.get(person.id, 0.0)
        tax_kwargs = {
            "tax_year": yearly.year,
            "province": province,
            "taxpayer_age": yearly.year - person.birth_date.year,
            "eligible_dividends": yearly.eligible_dividends_by_person.get(person.id, 0.0),
        }
        full_tax = calculator.calculate_tax(taxable_income=taxable_income, **tax_kwargs).total_tax
        base_tax = calculator.calculate_tax(taxable_income=max(taxable_income - gains, 0.0), **tax_kwargs).total_tax
        capital_gains_tax += max(full_tax - base_tax, 0.0)

    capital_gains_tax = min(capital_gains_tax, total_tax)
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
    person1_name = plan.household.person1.name.split()[0]
    year_context = f"{person1_name} is {yearly.person1_age}: {selected_year}"

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
        # Spending the plan could not fund: the only legitimate balancing source.
        "Unfunded Shortfall": max(-yearly.cash_flow_gap, 0.0),
    }
    source_amounts = {name: value for name, value in source_amounts.items() if _meets_display_threshold(value)}

    destination_amounts: dict[str, float] = _split_tax_destinations(yearly, plan)
    event_expense_destinations = _event_expense_destinations(yearly, plan, projection.years[0].year)
    regular_expenses = yearly.total_expenses - yearly.one_time_expense - yearly.recurring_expense
    destination_amounts["Expenses"] = max(regular_expenses, 0.0)
    destination_amounts.update(event_expense_destinations)
    destination_amounts["OAS Clawback"] = yearly.oas_clawback
    destination_amounts["Estate Costs"] = yearly.estate_total_costs
    destination_amounts["Real Asset Purchase"] = (
        sum(yearly.real_asset_purchase_prices.values(), 0.0) + yearly.real_asset_purchase_costs
    )
    destination_amounts["Real Asset Selling Costs"] = yearly.real_asset_selling_costs
    destination_amounts.update(_gross_deposits_by_group(yearly, plan))
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
                    "hovertemplate": f"{year_context}<br>%{{label}}<br>Total: $%{{value:,.0f}}<extra></extra>",
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
