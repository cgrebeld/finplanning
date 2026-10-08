import pytest
from finplanning_core.engine import ProjectionResult
from finplanning_core.models import HouseholdPlan
from finplanning_core.services import PlanningService

from app.components.year_grid import (
    _style_selected_year_row,
)
from app.formatters import projection_to_dataframe, style_cash_flow

pd = pytest.importorskip("pandas")


def _projection_and_plan() -> tuple[ProjectionResult, HouseholdPlan]:
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base", start_year=2025, end_year=2027)
    return projection, service.plan


def test_style_selected_year_row_adds_pink_border_css() -> None:
    projection, plan = _projection_and_plan()
    df = projection_to_dataframe(projection, plan)
    styled = style_cash_flow(df)
    highlighted = _style_selected_year_row(styled, selected_year=2025)
    html = highlighted.to_html()

    assert "#ff4da6" in html


def test_style_selected_year_row_is_noop_when_none() -> None:
    projection, plan = _projection_and_plan()
    df = projection_to_dataframe(projection, plan)
    styled = style_cash_flow(df)
    untouched = _style_selected_year_row(styled, selected_year=None)
    html = untouched.to_html()

    assert "#ff4da6" not in html
