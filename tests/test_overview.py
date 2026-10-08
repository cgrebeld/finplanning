from streamlit.testing.v1 import AppTest

_APP = """
import sys
sys.modules["streamlit_ace"] = None
import streamlit as st
from app.state import init_state, load_service, run_projection
init_state()
if st.session_state.get("service") is None:
    load_service("tests/fixtures/real-assets-estate.yaml")
    run_projection()
st.session_state["nav_section"] = "Overview"
from app.main import run_app
run_app()
"""


def test_overview_shows_estate_real_assets_and_earlier_settlement() -> None:
    at = AppTest.from_string(_APP, default_timeout=120)
    at.run()

    assert not at.exception
    labels = [metric.label for metric in at.metric]
    assert "Gross Estate (2048)" in labels
    assert "After-Tax Estate" in labels
    captions = " ".join(caption.value for caption in at.caption)
    assert "real assets add" in captions
    assert "Settlement after an earlier death, paid in 2039" in captions
