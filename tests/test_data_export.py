from types import SimpleNamespace

import pytest

from app.views import data_export


def test_cached_xlsx_builds_once_per_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(data_export, "st", SimpleNamespace(session_state={}))
    calls: list[object] = []

    def _build(projection: object, _service: object) -> bytes:
        calls.append(projection)
        return b"xlsx"

    first, second = object(), object()
    assert data_export._cached_xlsx("summary", _build, first, None) == b"xlsx"
    data_export._cached_xlsx("summary", _build, first, None)
    data_export._cached_xlsx("summary", _build, second, None)

    assert calls == [first, second]


def test_detailed_xlsx_builds_for_sample_plan() -> None:
    from finplanning_core.services import PlanningService

    service = PlanningService.from_yaml("examples/sample-plan.yaml")
    projection = service.run_projection(scenario_id="base")

    assert data_export._build_detailed_xlsx(projection, service.plan)[:2] == b"PK"


def test_flatten_rows_expands_dicts_and_unions_columns() -> None:
    rows = [{"year": 2030, "by_person": {"a": 1.0, "b": 2.0}}, {"year": 2031, "by_person": {"a": 3.0}}]

    assert data_export._flatten_rows(rows) == [
        {"year": 2030, "by_person_a": 1.0, "by_person_b": 2.0},
        {"year": 2031, "by_person_a": 3.0, "by_person_b": None},
    ]
