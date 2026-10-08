"""Portfolio profile and equity-region editing on the Edit Plan view."""

from pathlib import Path

import pytest
import yaml
from finplanning_core.services import PlanningService
from streamlit.testing.v1 import AppTest

from app.views.edit_plan import apply_portfolio_settings

SAMPLE = "examples/sample-plan.yaml"


def _accounts(text: str) -> dict[str, dict]:
    return {a["id"]: a for a in yaml.safe_load(text)["accounts"]}


def test_portfolio_settings_round_trip_through_the_engine(tmp_path) -> None:
    text = Path(SAMPLE).read_text(encoding="utf-8")
    plan_regions = {"CANADA": 0.3, "US": 0.5, "DEVELOPED_EX_NA": 0.15, "EMERGING": 0.05}
    updated = apply_portfolio_settings(
        text, "GLOBAL_CAD_2026_09", plan_regions, {"john-tfsa": {"CANADA": 1.0, "US": 0.0}}
    )
    path = tmp_path / "plan.yaml"
    path.write_text(updated, encoding="utf-8")
    plan = PlanningService.from_yaml(str(path)).plan
    by_id = {a.id: a for a in plan.accounts}

    assert plan.equity_region_weights(by_id["john-tfsa"]) == (1.0, 0.0, 0.0, 0.0)
    assert plan.equity_region_weights(by_id["joint-nonreg"]) == (0.3, 0.5, 0.15, 0.05)  # plan weights replace it


def test_portfolio_settings_reject_weights_not_summing_to_one() -> None:
    text = Path(SAMPLE).read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="sum to 0.9000"):
        apply_portfolio_settings(text, "GLOBAL_CAD_2026_09", {"CANADA": 0.4, "US": 0.5}, {})


def test_legacy_profile_drops_regions_and_global_drops_canadian_share() -> None:
    text = Path(SAMPLE).read_text(encoding="utf-8")
    legacy = apply_portfolio_settings(text, "LEGACY_US", {"CANADA": 1.0}, {"john-tfsa": {"CANADA": 1.0}})
    raw = yaml.safe_load(legacy)
    assert raw["assumptions"]["portfolio"] == {"profile": "LEGACY_US"}
    assert all("equity_regions" not in a for a in raw["accounts"])

    raw["accounts"][0]["canadian_equity_share"] = 0.2
    back = apply_portfolio_settings(yaml.safe_dump(raw), "GLOBAL_CAD_2026_09", None, {})
    assert all("canadian_equity_share" not in a for a in _accounts(back).values())


_EDIT_PLAN = """
import sys
sys.modules["streamlit_ace"] = None
import streamlit as st
from app.state import init_state, load_service
init_state()
if st.session_state.get("service") is None:
    load_service("examples/sample-plan.yaml")
st.session_state["nav_section"] = "Edit Plan"
from app.main import run_app
run_app()
"""


def test_edit_plan_form_applies_plan_equity_regions() -> None:
    at = AppTest.from_string(_EDIT_PLAN, default_timeout=120)
    at.run()
    assert at.selectbox[0].value == "GLOBAL_CAD_2026_09"

    at.checkbox[0].check().run()  # set plan weights; inputs start at MSCI ACWI
    at.number_input[0].set_value(0.129).run()  # CANADA
    at.number_input[1].set_value(0.5421).run()  # US
    next(b for b in at.button if b.label == "Apply portfolio settings").click().run()

    assert not at.exception
    plan = at.session_state["service"].plan
    assert plan.assumptions.portfolio.equity_regions["CANADA"] == pytest.approx(0.129)
    assert "canadian_equity_share" not in at.session_state["yaml_editor"]
