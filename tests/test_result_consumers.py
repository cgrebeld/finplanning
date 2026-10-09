"""Consumers of engine results: complete, unsupported, error and partial (non-FOUND) states.

Exported values must agree with the engine CLI's JSON. examples/sample-plan.yaml is a copy of the
engine's tests/testdata/sample-plan.yaml.
"""

import json
import subprocess
import sys
from types import SimpleNamespace

import pytest
from finplanning_core.risk import MonteCarloConfig
from finplanning_core.services import PlanningService
from streamlit.testing.v1 import AppTest

from app import state
from app.charts.gap_analysis import capacity_label, capacity_note
from app.components.summary_metrics import depletion_text
from app.views.data_export import results_summary
from app.views.monte_carlo import depletion_scope_text, mc_summary

SAMPLE = "examples/sample-plan.yaml"
NO_HOUSING_PROFILE = "tests/fixtures/real-assets-estate.yaml"  # residences lack a Monte Carlo profile
MC_ARGS = ["--set", "scenario_id=base", "--set", "n_iterations=200", "--set", "seed=42"]


def _cli(tool: str, plan: str, *args: str) -> dict:
    out = subprocess.run(
        [sys.executable, "-m", "finplanning_core.tools._impl.run_tool", tool, "--plan-file", plan, *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)


def _mc(plan: str):
    service = PlanningService.from_yaml(plan)
    return service, service.run_monte_carlo(scenario_id="base", config=MonteCarloConfig(n_iterations=200, seed=42))


@pytest.fixture(scope="module")
def sample():
    service = PlanningService.from_yaml(SAMPLE)
    return service, service.run_projection(scenario_id="base")


def test_projection_export_matches_cli_json(sample) -> None:
    service, projection = sample
    exported = results_summary(projection, service.manager.get_plan("base"))
    cli = _cli("run_projection", SAMPLE, "--set", "scenario_id=base")

    assert exported["metrics"] == cli["metrics"]
    assert [{key: row[key] for key in cli["yearly_summary"][0]} for row in exported["yearly_summary"]] == cli[
        "yearly_summary"
    ]
    assert exported["reporting_end_year"] == cli["yearly_summary"][-1]["year"]
    assert exported["estate"]["after_tax_real"] < exported["estate"]["after_tax_nominal"]
    assert exported["monte_carlo"] is None


def test_complete_monte_carlo_export_matches_cli_json(sample) -> None:
    service, projection = sample
    _, result = _mc(SAMPLE)
    exported = results_summary(projection, service.plan, result)["monte_carlo"]
    cli = _cli("run_monte_carlo", SAMPLE, *MC_ARGS)

    assert cli["status"] == exported["status"] == "COMPLETE"
    shared = set(exported) & set(cli)
    assert shared >= {"depletion_probability", "depletion_probability_interval", "percentiles", "risk_end_year"}
    assert {key: exported[key] for key in shared} == {key: cli[key] for key in shared}
    assert exported["reporting_end_year"] < exported["risk_end_year"]
    assert "GLOBAL_CAD_2026_09" in " ".join(service.plan.material_assumptions())


def test_unsupported_monte_carlo_has_no_numbers_and_matches_cli_json() -> None:
    _, result = _mc(NO_HOUSING_PROFILE)
    exported = mc_summary(result)
    cli = _cli("run_monte_carlo", NO_HOUSING_PROFILE, *MC_ARGS)

    assert cli["status"] == exported["status"] == "UNSUPPORTED"
    for key in ("n_iterations", "depletion_probability", "percentiles", "median_depletion_age", "unsupported_reasons"):
        assert exported[key] == cli[key], key
    assert exported["depletion_probability"] is None
    assert exported["n_iterations"] == 0


def test_error_states_report_without_a_result(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = _cli("run_monte_carlo", "tests/fixtures/real-assets-estate.yaml", "--set", "scenario_id=missing")
    assert cli["status"] == "ERROR"
    assert cli["depletion_probability"] is None
    assert cli["n_iterations"] == 0

    def _fail(**_kwargs: object) -> None:
        raise ValueError("Scenario not found: missing")

    session = {"service": SimpleNamespace(run_monte_carlo=_fail), "mc_result": object(), "mc_running": False}
    monkeypatch.setattr(state, "st", SimpleNamespace(session_state=session))
    state.run_monte_carlo(n_iterations=200)
    assert session["error"] == "Scenario not found: missing"
    assert session["mc_result"] is None
    assert session["mc_running"] is False


_MC_VIEW = """
import sys
sys.modules["streamlit_ace"] = None
from finplanning_core.risk import MonteCarloConfig
from finplanning_core.services import PlanningService
from app.views.monte_carlo import render_monte_carlo_view
service = PlanningService.from_yaml("{plan}")
result = service.run_monte_carlo(scenario_id="base", config=MonteCarloConfig(n_iterations=200, seed=42))
render_monte_carlo_view(result, service.plan)
"""


def test_monte_carlo_view_shows_horizons_units_and_profile() -> None:
    at = AppTest.from_string(_MC_VIEW.format(plan=SAMPLE), default_timeout=120)
    at.run()

    assert not at.exception
    metrics = {metric.label: metric.value for metric in at.metric}
    assert metrics["Depletion Probability (to 2082)"] == "28.0%"
    assert metrics["Simulated Paths"] == "200"
    assert "Median Liquid Net Worth (2067)" in metrics
    assert "Never" not in " ".join(metrics.values())
    text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    assert "2026 dollars" in text
    assert "GLOBAL_CAD_2026_09" in text
    assert "unhedged CAD" in text


def test_monte_carlo_view_shows_unsupported_state_without_numbers() -> None:
    at = AppTest.from_string(_MC_VIEW.format(plan=NO_HOUSING_PROFILE), default_timeout=120)
    at.run()

    assert not at.exception
    assert not at.metric
    assert "UNSUPPORTED" in at.warning[0].value


def test_depletion_text_states_the_simulated_scope(sample) -> None:
    _, projection = sample
    assert depletion_text(projection) == f"None through {projection.years[-1].year}"
    _, result = _mc(SAMPLE)
    assert depletion_scope_text(result.model_copy(update={"median_depletion_age": None})) == (
        "No path depleted in 200 simulated paths through 2082."
    )


@pytest.mark.parametrize(
    ("status", "label_prefix"),
    [("FOUND", "$"), ("UPPER_BOUND_NOT_FOUND", "At least $"), ("INFEASIBLE_AT_ZERO", None), ("NOT_EVALUATED", None)],
)
def test_partial_spending_capacity_is_never_unconditional(sample, status: str, label_prefix: str | None) -> None:
    service, projection = sample
    partial = projection.model_copy(update={"sustainable_spending_status": status})
    label = capacity_label(partial)
    if label_prefix is None:
        assert label is None
    else:
        assert label.startswith(label_prefix)
    exported = results_summary(partial, service.plan)
    assert exported["metrics"]["sustainable_spending_status"] == status
    assert exported["sustainable_spending_note"] == capacity_note(partial)
    if status != "FOUND":
        assert "lower bound" in capacity_note(partial) or label is None


_OVERVIEW = """
import sys
sys.modules["streamlit_ace"] = None
from finplanning_core.services import PlanningService
from app.views.overview import render_overview
service = PlanningService.from_yaml("examples/sample-plan.yaml")
projection = service.run_projection(scenario_id="base")
render_overview(projection.model_copy(update={{"sustainable_spending_status": "{status}"}}), service)
"""


def test_overview_withholds_capacity_when_infeasible() -> None:
    at = AppTest.from_string(_OVERVIEW.format(status="INFEASIBLE_AT_ZERO"), default_timeout=120)
    at.run()

    assert not at.exception
    assert any("no spending capacity" in w.value for w in at.warning)
    labels = [metric.label for metric in at.metric]
    assert "Final Liquid Net Worth (2067)" in labels
    assert "Final Household Assets" in labels


def test_landing_page_renders_without_a_plan() -> None:
    at = AppTest.from_string("from app.main import run_app\nrun_app()", default_timeout=60)
    at.run()

    assert not at.exception
    assert at.title[0].value == "Financial Planning Helper"
