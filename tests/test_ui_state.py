from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from finplanning_core.engine.projection import ProjectionResult, YearlyProjection
from finplanning_core.services.planning import PlanningService

from app import state


def _make_fake_service(base_scenario_id: str = "base") -> SimpleNamespace:
    persons = [
        SimpleNamespace(life_expectancy_age=95, birth_date=date(1970, 1, 1)),
        SimpleNamespace(life_expectancy_age=92, birth_date=date(1974, 6, 15)),
    ]
    plan = SimpleNamespace(base_scenario_id=base_scenario_id, persons=persons)
    return SimpleNamespace(plan=plan)


def _make_projection(years: list[int]) -> ProjectionResult:
    yearly = [
        YearlyProjection(
            year=year,
            person1_age=year - 1970,
            person2_age=None,
            total_non_reg=100000.0,
            total_rrsp_rrif=200000.0,
            total_tfsa=50000.0,
            total_net_worth=350000.0,
        )
        for year in years
    ]
    return ProjectionResult(
        scenario_id="base",
        years=yearly,
        final_net_worth=yearly[-1].total_net_worth,
        depletion_age=None,
    )


def test_load_service_resets_all_projection_controls(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    fake_st.session_state["scenario_id"] = "stale-scenario"
    fake_st.session_state["scenario_select"] = "stale-scenario"
    fake_st.session_state["start_year"] = 2030
    fake_st.session_state["start_year_input"] = 2030
    fake_st.session_state["end_year"] = 2060
    fake_st.session_state["end_year_input"] = 2060
    fake_st.session_state["mc_result"] = object()
    fake_st.session_state["mc_running"] = True

    fake_service = _make_fake_service()
    monkeypatch.setattr(
        PlanningService,
        "from_yaml",
        staticmethod(lambda _path: fake_service),
    )

    plan_file = tmp_path / "plan.yaml"
    plan_contents = "household:\n  name: Test\n"
    plan_file.write_text(plan_contents, encoding="utf-8")

    state.load_service(str(plan_file))

    expected_end_year = 1974 + 95
    today_year = date.today().year

    assert fake_st.session_state["service"] is fake_service
    assert fake_st.session_state["projection"] is None
    assert fake_st.session_state["mc_result"] is None
    assert fake_st.session_state["mc_running"] is False
    assert fake_st.session_state["scenario_id"] == "base"
    assert fake_st.session_state["scenario_select"] == "base"
    assert fake_st.session_state["start_year"] == today_year
    assert fake_st.session_state["start_year_input"] == today_year
    assert fake_st.session_state["end_year"] == expected_end_year
    assert fake_st.session_state["end_year_input"] == expected_end_year
    assert fake_st.session_state["yaml_text"] == plan_contents
    assert fake_st.session_state["yaml_applied"] == plan_contents
    assert fake_st.session_state["yaml_editor"] == plan_contents
    assert fake_st.session_state["error"] is None


def test_apply_yaml_edits_resets_controls_and_reprojects_when_projection_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    fake_st.session_state["scenario_id"] = "retire-early"
    fake_st.session_state["scenario_select"] = "retire-early"
    fake_st.session_state["start_year"] = 2040
    fake_st.session_state["start_year_input"] = 2040
    fake_st.session_state["end_year"] = 2080
    fake_st.session_state["end_year_input"] = 2080
    fake_st.session_state["projection"] = object()
    fake_st.session_state["mc_result"] = object()
    fake_st.session_state["mc_running"] = True

    fake_service = _make_fake_service(base_scenario_id="base")
    monkeypatch.setattr(
        PlanningService,
        "from_yaml",
        staticmethod(lambda _path: fake_service),
    )

    reprojection_called = {"value": False}

    def _fake_run_projection() -> None:
        reprojection_called["value"] = True

    monkeypatch.setattr(state, "run_projection", _fake_run_projection)

    edited_yaml = "household:\n  name: Edited\n"
    state.apply_yaml_edits(edited_yaml)

    expected_end_year = 1974 + 95
    today_year = date.today().year

    assert fake_st.session_state["service"] is fake_service
    assert fake_st.session_state["scenario_id"] == "base"
    assert fake_st.session_state["scenario_select"] == "base"
    assert fake_st.session_state["start_year"] == today_year
    assert fake_st.session_state["start_year_input"] == today_year
    assert fake_st.session_state["end_year"] == expected_end_year
    assert fake_st.session_state["end_year_input"] == expected_end_year
    assert fake_st.session_state["yaml_text"] == edited_yaml
    assert fake_st.session_state["yaml_applied"] == edited_yaml
    assert fake_st.session_state["projection"] is None
    assert fake_st.session_state["mc_result"] is None
    assert fake_st.session_state["mc_running"] is False
    assert fake_st.session_state["error"] is None
    assert reprojection_called["value"] is True


def test_apply_yaml_edits_does_not_reproject_without_active_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    fake_service = _make_fake_service(base_scenario_id="base")
    monkeypatch.setattr(
        PlanningService,
        "from_yaml",
        staticmethod(lambda _path: fake_service),
    )

    reprojection_called = {"value": False}

    def _fake_run_projection() -> None:
        reprojection_called["value"] = True

    monkeypatch.setattr(state, "run_projection", _fake_run_projection)

    edited_yaml = "household:\n  name: Edited\n"
    state.apply_yaml_edits(edited_yaml)

    assert fake_st.session_state["service"] is fake_service
    assert fake_st.session_state["projection"] is None
    assert fake_st.session_state["yaml_applied"] == edited_yaml
    assert fake_st.session_state["error"] is None
    assert reprojection_called["value"] is False


def test_apply_yaml_edits_rejects_content_over_100kb(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    called = {"value": False}

    def _raise_if_called(_path: str) -> SimpleNamespace:
        called["value"] = True
        raise AssertionError("from_yaml should not be called for oversized YAML")

    monkeypatch.setattr(
        PlanningService,
        "from_yaml",
        staticmethod(_raise_if_called),
    )

    oversized_yaml = "x" * (state.MAX_YAML_SIZE_BYTES + 1)
    state.apply_yaml_edits(oversized_yaml)

    assert called["value"] is False
    assert "exceeds" in (fake_st.session_state["error"] or "")
    assert str(state.MAX_YAML_SIZE_BYTES) in (fake_st.session_state["error"] or "")


def test_run_monte_carlo_rejects_iterations_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    called = {"value": False}

    def _fake_run_monte_carlo(**_kwargs: object) -> object:
        called["value"] = True
        return object()

    fake_service = SimpleNamespace(plan=_make_fake_service().plan, run_monte_carlo=_fake_run_monte_carlo)
    fake_st.session_state["service"] = fake_service

    state.run_monte_carlo(n_iterations=state.MAX_MC_ITERATIONS + 1)

    assert called["value"] is False
    assert "cannot exceed" in (fake_st.session_state["error"] or "")


def test_run_monte_carlo_rejects_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    called = {"value": False}

    def _fake_run_monte_carlo(**_kwargs: object) -> object:
        called["value"] = True
        return object()

    fake_service = SimpleNamespace(plan=_make_fake_service().plan, run_monte_carlo=_fake_run_monte_carlo)
    fake_st.session_state["service"] = fake_service
    fake_st.session_state["mc_running"] = True

    state.run_monte_carlo(n_iterations=1000)

    assert called["value"] is False
    assert "already running" in (fake_st.session_state["error"] or "")


def test_run_monte_carlo_passes_return_method_to_config(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    captured: dict[str, object] = {}

    def _fake_run_monte_carlo(**kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    fake_service = SimpleNamespace(plan=_make_fake_service().plan, run_monte_carlo=_fake_run_monte_carlo)
    fake_st.session_state["service"] = fake_service

    state.run_monte_carlo(n_iterations=200, return_method="parametric")

    config = captured.get("config")
    assert config is not None
    assert getattr(config, "return_method", None) == "parametric"
    assert fake_st.session_state["error"] is None


def test_run_projection_sets_default_selected_flow_year(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    projection = _make_projection([2025, 2026, 2027])
    fake_service = SimpleNamespace(run_projection=lambda **_kwargs: projection)
    fake_st.session_state["service"] = fake_service

    state.run_projection()

    assert fake_st.session_state["projection"] is projection
    assert fake_st.session_state["selected_flow_year"] == 2025


def test_run_projection_preserves_valid_selected_flow_year(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    projection = _make_projection([2025, 2026, 2027])
    fake_service = SimpleNamespace(run_projection=lambda **_kwargs: projection)
    fake_st.session_state["service"] = fake_service
    fake_st.session_state["selected_flow_year"] = 2026

    state.run_projection()

    assert fake_st.session_state["selected_flow_year"] == 2026
