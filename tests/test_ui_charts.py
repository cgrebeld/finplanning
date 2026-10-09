"""Tests for UI chart builders that do not require Streamlit runtime."""

import pytest
from finplanning_core.engine import ProjectionResult, YearlyProjection
from finplanning_core.models import HouseholdPlan
from finplanning_core.services import PlanningService

from app.charts.cash_flow_sankey import (
    DESTINATION_ORDER,
    MIN_DISPLAY_FLOW,
    SOURCE_ORDER,
    _recommended_sankey_height,
    build_cash_flow_sankey_figure,
)
from app.charts.net_worth import build_net_worth_figure
from app.charts.tax_heatmap import build_tax_heatmap_figure


def _make_projection_and_plan() -> tuple[ProjectionResult, HouseholdPlan]:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base", start_year=2025, end_year=2027)
    return projection, service.plan


def test_net_worth_figure_includes_selected_year_marker() -> None:
    projection, plan = _make_projection_and_plan()
    fig = build_net_worth_figure(projection, plan, selected_year=2026)

    annotation_texts = [ann.text for ann in fig.layout.annotations if ann.text is not None]
    assert any(text == "2026" for text in annotation_texts)


def test_net_worth_depletion_marker_uses_reported_year_with_remaining_assets() -> None:
    projection, plan = _make_projection_and_plan()
    assert all(year.total_net_worth > 0 for year in projection.years)
    projection = projection.model_copy(update={"depletion_year": 2026})
    fig = build_net_worth_figure(projection, plan)
    marker = next(ann for ann in fig.layout.annotations if ann.text == "Depletion (2026)")
    assert marker.x == 2026 - plan.household.person1.birth_date.year


def test_tax_heatmap_includes_selected_year_marker_line() -> None:
    projection, plan = _make_projection_and_plan()
    fig = build_tax_heatmap_figure(projection, plan, selected_year=2026)

    assert fig.layout.shapes is not None
    assert len(fig.layout.shapes) >= 1


def test_cash_flow_sankey_balances_at_available_cash_node() -> None:
    projection, plan = _make_projection_and_plan()
    fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2025)

    sankey = fig.data[0]
    labels = list(sankey.node.label)
    sources = list(sankey.link.source)
    targets = list(sankey.link.target)
    values = [float(v) for v in sankey.link.value]

    hub_index = labels.index("Available Cash")
    inbound = sum(v for s, t, v in zip(sources, targets, values, strict=True) if t == hub_index)
    outbound = sum(v for s, t, v in zip(sources, targets, values, strict=True) if s == hub_index)

    assert inbound == pytest.approx(outbound, rel=1e-9, abs=1e-6)


def test_cash_flow_sankey_raises_for_unknown_year() -> None:
    projection, plan = _make_projection_and_plan()

    with pytest.raises(ValueError, match="not found in projection"):
        build_cash_flow_sankey_figure(projection, plan, selected_year=1900)


def test_cash_flow_sankey_colors_income_tax_node_red() -> None:
    projection, plan = _make_projection_and_plan()
    fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2025)

    sankey = fig.data[0]
    labels = list(sankey.node.label)
    colors = list(sankey.node.color)
    tax_index = labels.index("Income Tax")

    assert colors[tax_index] == "red"


def test_cash_flow_sankey_node_order_stable_across_years() -> None:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base", start_year=2025, end_year=2031)
    plan = service.plan

    fig_2025 = build_cash_flow_sankey_figure(projection, plan, selected_year=2025)
    fig_2030 = build_cash_flow_sankey_figure(projection, plan, selected_year=2030)

    sankey_2025 = fig_2025.data[0]
    sankey_2030 = fig_2030.data[0]

    labels_2025 = list(sankey_2025.node.label)
    labels_2030 = list(sankey_2030.node.label)

    sources_2025 = [label for label in labels_2025 if label in SOURCE_ORDER]
    sources_2030 = [label for label in labels_2030 if label in SOURCE_ORDER]
    destinations_2025 = [label for label in labels_2025 if label in DESTINATION_ORDER]
    destinations_2030 = [label for label in labels_2030 if label in DESTINATION_ORDER]

    assert sources_2025 == sorted(sources_2025, key=SOURCE_ORDER.index)
    assert sources_2030 == sorted(sources_2030, key=SOURCE_ORDER.index)
    assert destinations_2025 == sorted(destinations_2025, key=DESTINATION_ORDER.index)
    assert destinations_2030 == sorted(destinations_2030, key=DESTINATION_ORDER.index)


def test_sankey_height_scales_with_node_count() -> None:
    small = _recommended_sankey_height(2, 2)
    medium = _recommended_sankey_height(6, 4)
    large = _recommended_sankey_height(20, 20)

    assert small == 500
    assert medium > small
    assert large == 920


def test_cash_flow_sankey_zoom_scale_increases_height() -> None:
    projection, plan = _make_projection_and_plan()
    base_fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2025, zoom_scale=1.0)
    zoom_fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2025, zoom_scale=1.6)

    assert zoom_fig.layout.height > base_fig.layout.height


def test_cash_flow_sankey_omits_sub_five_dollar_balancing_flow() -> None:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    plan = service.plan
    year = YearlyProjection(
        year=2030,
        person1_age=60,
        person2_age=None,
        employment_income=100.0,
        total_tax=0.0,
        total_expenses=96.0,
        total_net_worth=1000.0,
    )
    projection = ProjectionResult(
        scenario_id="base",
        years=[year],
        final_net_worth=1000.0,
        depletion_age=None,
    )

    fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2030)
    labels = list(fig.data[0].node.label)

    assert MIN_DISPLAY_FLOW == 5.0
    assert "Unallocated Cash" not in labels
    assert "Balance Adjustment" not in labels


FIXTURE_PLAN = "tests/fixtures/real-assets-estate.yaml"


@pytest.mark.parametrize(
    "plan_path",
    [
        "examples/sample-plan.yaml",
        "examples/bc-top-1pct-couple-40.yaml",
        "examples/canada-typical-40-couple.yaml",
        FIXTURE_PLAN,
    ],
)
def test_cash_flow_sankey_balances_every_year_without_plugs(plan_path: str) -> None:
    service = PlanningService.from_yaml(plan_path)
    for scenario_id in service.manager.scenario_ids:
        projection = service.run_projection(scenario_id=scenario_id)
        for year in projection.years:
            labels = list(build_cash_flow_sankey_figure(projection, service.plan, year.year).data[0].node.label)
            assert "Balance Adjustment" not in labels, (plan_path, scenario_id, year.year)
            assert "Unallocated Cash" not in labels, (plan_path, scenario_id, year.year)


def _labels_and_flows(projection: ProjectionResult, plan: HouseholdPlan, year: int) -> dict[str, float]:
    sankey = build_cash_flow_sankey_figure(projection, plan, year).data[0]
    labels = list(sankey.node.label)
    hub = labels.index("Available Cash")
    return {
        labels[t] if s == hub else labels[s]: float(v)
        for s, t, v in zip(sankey.link.source, sankey.link.target, sankey.link.value, strict=True)
    }


def test_cash_flow_sankey_shows_real_asset_oas_clawback_and_estate_flows() -> None:
    service = PlanningService.from_yaml(FIXTURE_PLAN)
    projection = service.run_projection(scenario_id="base")
    by_year = {y.year: y for y in projection.years}

    purchase = _labels_and_flows(projection, service.plan, 2028)
    assert purchase["Real Asset Purchase"] == pytest.approx(
        sum(by_year[2028].real_asset_purchase_prices.values()) + by_year[2028].real_asset_purchase_costs
    )

    sale = _labels_and_flows(projection, service.plan, 2033)
    assert sale["Real Asset Sale"] == pytest.approx(by_year[2033].real_asset_sale_proceeds)
    assert sale["Real Asset Selling Costs"] == pytest.approx(by_year[2033].real_asset_selling_costs)

    clawback_year = next(y for y in projection.years if y.oas_clawback > 0)
    assert _labels_and_flows(projection, service.plan, clawback_year.year)["OAS Clawback"] == pytest.approx(
        clawback_year.oas_clawback
    )

    estate_year = next(y for y in projection.years if y.estate_total_costs > 0)
    estate = _labels_and_flows(projection, service.plan, estate_year.year)
    assert estate["Estate Costs"] == pytest.approx(estate_year.estate_total_costs)
    assert estate["Estate Settlement Tax"] == pytest.approx(estate_year.estate_settlement_tax)
    assert estate["Estate Settlement Draw"] > 0


def test_cash_flow_sankey_includes_named_one_time_and_recurring_expense_streams() -> None:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    extended = service.run_projection(
        scenario_id="base",
        start_year=2025,
        end_year=2028,
    )
    fig = build_cash_flow_sankey_figure(extended, service.plan, selected_year=2028)
    labels = list(fig.data[0].node.label)

    assert "One-Time: New Roof" in labels
    assert "Recurring: Home Renovation" in labels


def test_cash_flow_sankey_expenses_hover_lists_engine_components() -> None:
    projection, plan = _make_projection_and_plan()
    fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2025)
    node = fig.data[0].node
    details = node.customdata[list(node.label).index("Expenses")]
    yearly = projection.years[0]

    for expense in plan.expenses:
        assert f"{expense.name}: ${yearly.expense_amounts[expense.id]:,.0f}" in details
    assert "%{customdata}" in node.hovertemplate


def test_cash_flow_sankey_includes_capital_gains_tax_destination_when_applicable() -> None:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base", start_year=2025, end_year=2028)
    fig = build_cash_flow_sankey_figure(projection, service.plan, selected_year=2028)
    labels = list(fig.data[0].node.label)

    assert "Capital Gains Tax" in labels


def test_capital_gains_tax_comes_from_the_engine_per_person_amounts() -> None:
    from app.charts.cash_flow_sankey import _split_tax_destinations

    year = YearlyProjection(
        year=2030,
        person1_age=60,
        person2_age=58,
        total_tax=60000.0,
        capital_gains_tax_by_person={"john": 0.0, "jane": 1500.0},
    )

    split = _split_tax_destinations(year)

    assert split["Capital Gains Tax"] == pytest.approx(1500.0)
    assert split["Income Tax"] == pytest.approx(58500.0)


def test_cash_flow_sankey_links_are_translucent() -> None:
    projection, plan = _make_projection_and_plan()
    fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2025)

    assert all(color.startswith("rgba(") and color.endswith(", 0.25)") for color in fig.data[0].link.color)


def test_named_expense_streams_use_the_engine_per_item_amounts() -> None:
    from app.charts.cash_flow_sankey import _event_expense_destinations

    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base", start_year=2025, end_year=2028)
    year = next(y for y in projection.years if y.year == 2028)

    destinations = _event_expense_destinations(year, service.plan)

    one_time = sum(v for k, v in destinations.items() if k.startswith("One-Time: "))
    recurring = sum(v for k, v in destinations.items() if k.startswith("Recurring: "))
    assert one_time == pytest.approx(year.one_time_expense)
    assert recurring == pytest.approx(year.recurring_expense)
    assert destinations["One-Time: New Roof"] > 0


def test_net_worth_figure_stacks_real_assets_into_total() -> None:
    service = PlanningService.from_yaml(FIXTURE_PLAN)
    projection = service.run_projection(scenario_id="base")

    fig = build_net_worth_figure(projection, service.plan)
    traces = {trace.name: trace for trace in fig.data}

    assert list(traces["Real Assets"].y) == [y.total_real_asset_value for y in projection.years]
    assert list(traces["Total"].y) == pytest.approx([y.total_household_asset_value for y in projection.years])


def test_net_worth_figure_omits_real_assets_when_plan_has_none() -> None:
    service = PlanningService.from_yaml("examples/canada-typical-40-couple.yaml")
    projection, plan = service.run_projection(scenario_id="base"), service.plan
    assert "Real Assets" not in {trace.name for trace in build_net_worth_figure(projection, plan).data}


def test_expense_components_label_carrying_costs_and_adjustment() -> None:
    from app.charts.cash_flow_sankey import _regular_expense_components

    plan = PlanningService.from_yaml("examples/sample-plan.yaml").plan
    expense = plan.expenses[0]
    year = YearlyProjection(
        year=2030,
        person1_age=60,
        person2_age=58,
        expense_amounts={expense.id: 1000.0, "unknown-id": 50.0},
        real_asset_carrying_costs_by_asset={"cabin": 200.0},
        expense_delta=-300.0,
    )

    assert _regular_expense_components(year, plan) == {
        expense.name: 1000.0,
        "unknown-id": 50.0,
        "cabin Carrying Costs": 200.0,
        "Spending Adjustment": -300.0,
    }
