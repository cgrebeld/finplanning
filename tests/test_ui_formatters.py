"""Tests for src/ui/formatters — pure pandas, no Streamlit required."""

import inspect

import pytest

pd = pytest.importorskip("pandas")

from finplanning_core.engine import ProjectionResult  # noqa: E402
from finplanning_core.services import PlanningService  # noqa: E402

from app.formatters import projection_to_dataframe, style_cash_flow  # noqa: E402


def _make_result(person2_age: int | None = 53) -> tuple[ProjectionResult, PlanningService]:
    """Load the sample plan and run a short projection."""
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    result = service.run_projection(scenario_id="base", start_year=2025, end_year=2027)
    return result, service


def test_dataframe_row_count() -> None:
    result, service = _make_result()
    df = projection_to_dataframe(result, service.plan)
    assert len(df) == len(result.years)


def test_dataframe_has_expected_columns() -> None:
    result, service = _make_result()
    df = projection_to_dataframe(result, service.plan)
    expected = {
        "Year",
        "Income",
        "Expenses",
        "Tax",
        "Net Income",
        "Cash Flow",
        "Withdrawals",
        "Non-Reg",
        "RRSP/RRIF",
        "TFSA",
        "Net Worth",
    }
    assert expected.issubset(set(df.columns))


def test_person_names_in_age_columns() -> None:
    result, service = _make_result()
    df = projection_to_dataframe(result, service.plan)
    person1_name = service.plan.household.person1.name.split()[0]
    assert f"{person1_name} Age" in df.columns
    person2 = service.plan.household.person2
    if person2 is not None:
        person2_name = person2.name.split()[0]
        assert f"{person2_name} Age" in df.columns


def test_single_person_drops_second_age_column() -> None:
    """When person2 is None, the second age column is absent."""
    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    # Temporarily remove person2 for this test
    plan = service.plan
    original_person2 = plan.household.person2
    plan.household.person2 = None

    result = service.run_projection(scenario_id="base", start_year=2025, end_year=2026)
    df = projection_to_dataframe(result, plan)

    age_cols = [c for c in df.columns if c.endswith(" Age")]
    assert len(age_cols) == 1

    # Restore
    plan.household.person2 = original_person2


def test_style_cash_flow_returns_styler() -> None:
    result, service = _make_result()
    df = projection_to_dataframe(result, service.plan)
    styler = style_cash_flow(df)
    assert isinstance(styler, pd.io.formats.style.Styler)


def test_dataframe_values_are_float() -> None:
    """Ensure Decimal values have been converted to float for pandas."""
    result, service = _make_result()
    df = projection_to_dataframe(result, service.plan)
    net_worth_vals = df["Net Worth"]
    for val in net_worth_vals:
        assert isinstance(val, float)


def test_render_functions_importable_with_correct_params() -> None:
    """Verify component render function signatures are importable."""
    from app.components.summary_metrics import render_summary_metrics
    from app.components.year_grid import render_year_grid

    sig_grid = inspect.signature(render_year_grid)
    assert "projection" in sig_grid.parameters
    assert "plan" in sig_grid.parameters

    sig_summary = inspect.signature(render_summary_metrics)
    assert "projection" in sig_summary.parameters
