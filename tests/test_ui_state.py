from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from finplanning_core.engine import ProjectionResult, YearlyProjection
from finplanning_core.services import PlanningService

from app import state


def _make_fake_service(base_scenario_id: str = "base", scenario_ids: list[str] | None = None) -> SimpleNamespace:
    persons = [
        SimpleNamespace(life_expectancy_age=95, birth_date=date(1970, 1, 1)),
        SimpleNamespace(life_expectancy_age=92, birth_date=date(1974, 6, 15)),
    ]
    plan = SimpleNamespace(base_scenario_id=base_scenario_id, persons=persons)
    manager = SimpleNamespace(scenario_ids=scenario_ids or [base_scenario_id])
    return SimpleNamespace(plan=plan, manager=manager)


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

    expected_end_year = 1974 + 92  # latest of 1970+95, 1974+92 is 2066
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
    assert fake_st.session_state["yaml_edit_error"] is None


def _seed_custom_controls(session_state: dict) -> None:
    session_state["scenario_id"] = "retire-early"
    session_state["scenario_select"] = "retire-early"
    session_state["start_year"] = 2040
    session_state["start_year_input"] = 2040
    session_state["end_year"] = 2080
    session_state["end_year_input"] = 2080
    session_state["projection"] = object()
    session_state["mc_result"] = object()
    session_state["mc_running"] = True


def test_apply_yaml_edits_keeps_controls_and_reprojects_when_projection_is_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()
    _seed_custom_controls(fake_st.session_state)

    fake_service = _make_fake_service(base_scenario_id="base", scenario_ids=["base", "retire-early"])
    monkeypatch.setattr(PlanningService, "from_yaml", staticmethod(lambda _path: fake_service))

    reprojected_with: list[tuple[object, object, object]] = []

    def _fake_run_projection() -> None:
        ss = fake_st.session_state
        reprojected_with.append((ss["scenario_id"], ss["start_year"], ss["end_year"]))

    monkeypatch.setattr(state, "run_projection", _fake_run_projection)

    edited_yaml = "household:\n  name: Edited\n"
    state.apply_yaml_edits(edited_yaml)

    assert fake_st.session_state["service"] is fake_service
    assert fake_st.session_state["scenario_select"] == "retire-early"
    assert fake_st.session_state["start_year_input"] == 2040
    assert fake_st.session_state["end_year_input"] == 2080
    assert fake_st.session_state["yaml_text"] == edited_yaml
    assert fake_st.session_state["yaml_applied"] == edited_yaml
    assert fake_st.session_state["projection"] is None
    assert fake_st.session_state["mc_result"] is None
    assert fake_st.session_state["mc_running"] is False
    assert fake_st.session_state["error"] is None
    assert reprojected_with == [("retire-early", 2040, 2080)]
    assert "_nav_after_run" not in fake_st.session_state


def test_apply_yaml_edits_resets_controls_when_selected_scenario_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()
    _seed_custom_controls(fake_st.session_state)

    fake_service = _make_fake_service(base_scenario_id="base")
    monkeypatch.setattr(PlanningService, "from_yaml", staticmethod(lambda _path: fake_service))
    monkeypatch.setattr(state, "run_projection", lambda: None)

    state.apply_yaml_edits("household:\n  name: Edited\n")

    assert fake_st.session_state["scenario_id"] == "base"
    assert fake_st.session_state["scenario_select"] == "base"
    assert fake_st.session_state["start_year"] == date.today().year
    assert fake_st.session_state["end_year"] == 1974 + 92


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

    reprojection_called = False

    def _fake_run_projection() -> None:
        nonlocal reprojection_called
        reprojection_called = True

    monkeypatch.setattr(state, "run_projection", _fake_run_projection)

    edited_yaml = "household:\n  name: Edited\n"
    state.apply_yaml_edits(edited_yaml)

    assert fake_st.session_state["service"] is fake_service
    assert fake_st.session_state["projection"] is None
    assert fake_st.session_state["yaml_applied"] == edited_yaml
    assert fake_st.session_state["yaml_editor"] == edited_yaml
    assert fake_st.session_state["error"] is None
    assert reprojection_called is False


def test_apply_yaml_edits_rejects_content_over_100kb(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    from_yaml_called = False

    def _raise_if_called(_path: str) -> SimpleNamespace:
        nonlocal from_yaml_called
        from_yaml_called = True
        raise AssertionError("from_yaml should not be called for oversized YAML")

    monkeypatch.setattr(
        PlanningService,
        "from_yaml",
        staticmethod(_raise_if_called),
    )

    oversized_yaml = "x" * (state.MAX_YAML_SIZE_BYTES + 1)
    state.apply_yaml_edits(oversized_yaml)

    assert from_yaml_called is False
    assert "exceeds" in (fake_st.session_state["yaml_edit_error"] or "")
    assert str(state.MAX_YAML_SIZE_BYTES) in (fake_st.session_state["yaml_edit_error"] or "")
    assert fake_st.session_state.get("error") is None


def test_run_monte_carlo_rejects_iterations_over_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    mc_called = False

    def _fake_run_monte_carlo(**_kwargs: object) -> object:
        nonlocal mc_called
        mc_called = True
        return object()

    fake_service = SimpleNamespace(plan=_make_fake_service().plan, run_monte_carlo=_fake_run_monte_carlo)
    fake_st.session_state["service"] = fake_service

    state.run_monte_carlo(n_iterations=state.MAX_MC_ITERATIONS + 1)

    assert mc_called is False
    assert "cannot exceed" in (fake_st.session_state["error"] or "")


def test_run_monte_carlo_rejects_when_already_running(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    mc_called = False

    def _fake_run_monte_carlo(**_kwargs: object) -> object:
        nonlocal mc_called
        mc_called = True
        return object()

    fake_service = SimpleNamespace(plan=_make_fake_service().plan, run_monte_carlo=_fake_run_monte_carlo)
    fake_st.session_state["service"] = fake_service
    fake_st.session_state["mc_running"] = True

    state.run_monte_carlo(n_iterations=1000)

    assert mc_called is False
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


def test_run_monte_carlo_clears_running_flag_when_interrupted(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit.runtime.scriptrunner_utils.exceptions import StopException

    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    def _interrupted(**_kwargs: object) -> object:
        raise StopException()  # BaseException, as raised by a Streamlit rerun/stop

    fake_st.session_state["service"] = SimpleNamespace(run_monte_carlo=_interrupted)

    with pytest.raises(StopException):
        state.run_monte_carlo()

    assert fake_st.session_state["mc_running"] is False


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


def test_apply_yaml_edits_sets_yaml_edit_error_on_parse_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    def _raise(_path: str) -> None:
        raise ValueError("bad schema")

    monkeypatch.setattr(PlanningService, "from_yaml", staticmethod(_raise))

    state.apply_yaml_edits("invalid: yaml: content")

    assert "bad schema" in (fake_st.session_state["yaml_edit_error"] or "")
    assert fake_st.session_state.get("error") is None
    # yaml_applied must NOT be updated when parse fails
    assert fake_st.session_state["yaml_applied"] == ""


def test_apply_yaml_edits_clears_yaml_edit_error_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()
    fake_st.session_state["yaml_edit_error"] = "previous error"

    fake_service = _make_fake_service()
    monkeypatch.setattr(PlanningService, "from_yaml", staticmethod(lambda _path: fake_service))
    monkeypatch.setattr(state, "run_projection", lambda: None)

    state.apply_yaml_edits("household:\n  name: OK\n")

    assert fake_st.session_state["yaml_edit_error"] is None


def test_load_service_from_yaml_text_sets_all_state_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    fake_service = _make_fake_service()
    monkeypatch.setattr(PlanningService, "from_yaml", staticmethod(lambda _path: fake_service))

    yaml_content = "household:\n  name: Test\n"
    state.load_service_from_yaml_text(yaml_content)

    expected_end_year = 1974 + 92  # latest of 1970+95, 1974+92 is 2066
    today_year = date.today().year

    assert fake_st.session_state["service"] is fake_service
    assert fake_st.session_state["projection"] is None
    assert fake_st.session_state["mc_result"] is None
    assert fake_st.session_state["mc_running"] is False
    assert fake_st.session_state["error"] is None
    assert fake_st.session_state["yaml_text"] == yaml_content
    assert fake_st.session_state["yaml_applied"] == yaml_content
    assert fake_st.session_state["yaml_editor"] == yaml_content
    assert fake_st.session_state["scenario_id"] == "base"
    assert fake_st.session_state["start_year"] == today_year
    assert fake_st.session_state["end_year"] == expected_end_year
    assert fake_st.session_state["plan_path"] == ""
    assert fake_st.session_state["yaml_edit_error"] is None
    assert fake_st.session_state["editor_version"] == 1


def test_load_service_from_yaml_text_rejects_oversized_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    oversized = "x" * (state.MAX_YAML_SIZE_BYTES + 1)
    state.load_service_from_yaml_text(oversized)

    assert fake_st.session_state["service"] is None
    assert "exceeds" in (fake_st.session_state["error"] or "")


def test_load_service_from_yaml_text_sets_error_on_parse_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()

    def _raise(_path: str) -> None:
        raise ValueError("invalid plan")

    monkeypatch.setattr(PlanningService, "from_yaml", staticmethod(_raise))

    state.load_service_from_yaml_text("bad: yaml")

    assert fake_st.session_state["service"] is None
    assert "invalid plan" in (fake_st.session_state["error"] or "")


def test_run_projection_records_the_params_it_ran_with(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_st = SimpleNamespace(session_state={})
    monkeypatch.setattr(state, "st", fake_st)
    state.init_state()
    fake_st.session_state.update(scenario_id="retire-early", start_year=2030, end_year=2060)
    projection = _make_projection([2030, 2031])
    fake_st.session_state["service"] = SimpleNamespace(run_projection=lambda **_kwargs: projection)

    state.run_projection()
    assert fake_st.session_state["projection_params"] == ("retire-early", 2030, 2060)
    assert state.current_run_params() == ("retire-early", 2030, 2060)

    fake_st.session_state["start_year"] = 2035
    assert state.current_run_params() != fake_st.session_state["projection_params"]
