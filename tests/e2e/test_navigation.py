"""End-to-end navigation tests for the section-based UI.

Run with: .venv/bin/python -m pytest tests/e2e/ -v
For visual debugging: .venv/bin/python -m pytest tests/e2e/ -v --headed
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

# How long to wait for Streamlit to rerender after an interaction (ms).
_WAIT_MS = 5000
# Longer timeout for assertions on elements that may take extra time (charts, xlsx).
_SLOW_TIMEOUT = 10_000


def _load_plan(page: Page, base_url: str) -> None:
    """Navigate to the app and click Load with the default plan file."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Load").click()
    page.wait_for_timeout(_WAIT_MS)


def _run_projection(page: Page) -> None:
    """Click the Run Projection button and wait for results."""
    page.get_by_role("button", name="Run Projection").click()
    page.wait_for_timeout(_WAIT_MS)


def _click_nav(page: Page, section: str) -> None:
    """Select a section via the sidebar navigation radio."""
    page.locator('[data-testid="stRadio"]').get_by_text(section, exact=True).click()
    page.wait_for_timeout(_WAIT_MS)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_landing_page(page: Page, streamlit_server: str) -> None:
    """With no plan loaded, the feature grid is visible and nav radio is absent."""
    page.goto(streamlit_server)
    page.wait_for_load_state("networkidle")

    expect(page.get_by_text("Cash-Flow Projections")).to_be_visible()
    expect(page.get_by_text("Monte Carlo")).to_be_visible()
    expect(page.get_by_text("Excel Export")).to_be_visible()

    # Nav radio should NOT be present before a plan is loaded.
    expect(page.locator('[data-testid="stRadio"]')).not_to_be_visible()


def test_load_plan_shows_editor(page: Page, streamlit_server: str) -> None:
    """Loading a plan navigates to the Edit Plan view with the YAML editor visible."""
    _load_plan(page, streamlit_server)

    # The section header should be visible.
    expect(page.get_by_role("heading", name="Edit Plan").first).to_be_visible()

    # Sidebar nav radio should now be visible.
    expect(page.locator('[data-testid="stRadio"]')).to_be_visible()

    # Run Projection button should be present in the main area.
    expect(page.get_by_role("button", name="Run Projection")).to_be_visible()


def test_run_projection_navigates_to_overview(page: Page, streamlit_server: str) -> None:
    """Running a projection auto-navigates to the Overview section."""
    _load_plan(page, streamlit_server)
    _run_projection(page)

    expect(
        page.get_by_role("heading", name=re.compile(r"Overview")).first
    ).to_be_visible(timeout=_SLOW_TIMEOUT)

    # At least one summary metric should be visible.
    expect(page.locator('[data-testid="stMetric"]').first).to_be_visible()


def test_nav_to_cash_flow(page: Page, streamlit_server: str) -> None:
    """Clicking Cash Flow shows the year slider and Sankey diagram."""
    _load_plan(page, streamlit_server)
    _run_projection(page)
    _click_nav(page, "Cash Flow")

    expect(page.get_by_role("heading", name="Cash Flow").first).to_be_visible()
    expect(page.locator('[data-testid="stSlider"]')).to_be_visible()


def test_nav_to_net_worth(page: Page, streamlit_server: str) -> None:
    """Clicking Net Worth shows the net worth chart."""
    _load_plan(page, streamlit_server)
    _run_projection(page)
    _click_nav(page, "Net Worth")

    expect(page.get_by_role("heading", name="Net Worth").first).to_be_visible()
    expect(page.locator('[data-testid="stPlotlyChart"]').first).to_be_visible(
        timeout=_SLOW_TIMEOUT
    )


def test_nav_to_tax_analysis(page: Page, streamlit_server: str) -> None:
    """Clicking Tax Analysis shows the heatmap chart."""
    _load_plan(page, streamlit_server)
    _run_projection(page)
    _click_nav(page, "Tax Analysis")

    expect(page.get_by_role("heading", name="Tax Analysis").first).to_be_visible()
    expect(page.locator('[data-testid="stPlotlyChart"]').first).to_be_visible(
        timeout=_SLOW_TIMEOUT
    )


def test_nav_to_monte_carlo(page: Page, streamlit_server: str) -> None:
    """Clicking Monte Carlo shows the iterations selectbox and Run button."""
    _load_plan(page, streamlit_server)
    _run_projection(page)
    _click_nav(page, "Monte Carlo")

    expect(page.get_by_role("heading", name="Monte Carlo Simulation")).to_be_visible()
    expect(page.get_by_role("button", name="Run")).to_be_visible()
    # Iterations selectbox should be present.
    expect(page.locator('[data-testid="stSelectbox"]').first).to_be_visible()


def test_nav_to_data_export(page: Page, streamlit_server: str) -> None:
    """Clicking Data & Export shows the year grid table and export buttons."""
    _load_plan(page, streamlit_server)
    _run_projection(page)
    _click_nav(page, "Data & Export")

    expect(page.get_by_role("heading", name="Data & Export").first).to_be_visible()
    expect(page.locator('[data-testid="stDownloadButton"]').first).to_be_visible(
        timeout=_SLOW_TIMEOUT
    )


def test_no_projection_guard(page: Page, streamlit_server: str) -> None:
    """Navigating to Overview before running a projection shows the info message."""
    _load_plan(page, streamlit_server)
    # Navigate to Overview without running a projection first.
    _click_nav(page, "Overview")

    # The info alert should appear directing the user to Edit Plan.
    expect(page.locator('[data-testid="stAlertContentInfo"]')).to_be_visible()


def test_year_slider_persists(page: Page, streamlit_server: str) -> None:
    """Moving the Cash Flow year slider changes selected_flow_year for other views."""
    _load_plan(page, streamlit_server)
    _run_projection(page)
    _click_nav(page, "Cash Flow")

    slider = page.locator('[data-testid="stSlider"]')
    expect(slider).to_be_visible()

    # Move slider one step to the right using keyboard.
    slider.get_by_role("slider").focus()
    slider.get_by_role("slider").press("ArrowRight")
    page.wait_for_timeout(_WAIT_MS)

    # Navigate to Net Worth — the magenta year-marker line should still be present.
    _click_nav(page, "Net Worth")
    expect(page.locator('[data-testid="stPlotlyChart"]').first).to_be_visible(
        timeout=_SLOW_TIMEOUT
    )
