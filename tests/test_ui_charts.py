"""Tests for UI chart builders that do not require Streamlit runtime."""

import pytest
from finplanning_core.engine.projection import ProjectionResult, YearlyProjection
from finplanning_core.models.plan import HouseholdPlan
from finplanning_core.services.planning import PlanningService

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


def test_cash_flow_sankey_prioritizes_portfolio_reinvestment_before_unallocated_cash() -> None:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    plan = service.plan
    year = YearlyProjection(
        year=2035,
        person1_age=65,
        person2_age=None,
        employment_income=100.0,
        portfolio_dividend_income=10.0,
        portfolio_interest_income=10.0,
        total_tax=0.0,
        total_expenses=100.0,
        total_net_worth=1000.0,
    )
    projection = ProjectionResult(
        scenario_id="base",
        years=[year],
        final_net_worth=1000.0,
        depletion_age=None,
    )

    fig = build_cash_flow_sankey_figure(projection, plan, selected_year=2035)
    labels = list(fig.data[0].node.label)

    assert "Portfolio Reinvestment" in labels
    assert "Unallocated Cash" not in labels


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


def test_cash_flow_sankey_includes_capital_gains_tax_destination_when_applicable() -> None:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base", start_year=2025, end_year=2028)
    fig = build_cash_flow_sankey_figure(projection, service.plan, selected_year=2028)
    labels = list(fig.data[0].node.label)

    assert "Capital Gains Tax" in labels
