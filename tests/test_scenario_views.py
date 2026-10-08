from streamlit.testing.v1 import AppTest

_APP = """
import sys
sys.modules["streamlit_ace"] = None
import streamlit as st
from app.state import init_state, load_service, run_projection
init_state()
if st.session_state.get("service") is None:
    load_service("examples/sample-plan.yaml")
    st.session_state["service"].manager.apply_override("early-retire", "one_time_events.roof.name", "Scenario Roof")
    st.session_state["scenario_id"] = "early-retire"
    run_projection()
    st.session_state["selected_flow_year"] = 2028
st.session_state["nav_section"] = "Cash Flow"
from app.main import run_app
run_app()
"""


def test_cash_flow_view_uses_the_projected_scenarios_plan() -> None:
    at = AppTest.from_string(_APP, default_timeout=120)
    at.run()

    assert not at.exception
    assert at.session_state["projection"].scenario_id == "early-retire"
    sankey_spec = at.get("plotly_chart")[0].proto.spec
    assert "One-Time: Scenario Roof" in sankey_spec
    assert "One-Time: New Roof" not in sankey_spec
