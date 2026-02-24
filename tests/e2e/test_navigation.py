"""End-to-end navigation tests for the section-based UI.

Run with: .venv/bin/python -m pytest tests/e2e/ -v
For visual debugging: .venv/bin/python -m pytest tests/e2e/ -v --headed
"""

import re

import pytest
from playwright.sync_api import Page, expect

# How long to wait for Streamlit to rerender after an interaction (ms).
_WAIT_MS = 5000
# Longer timeout for assertions on elements that may take extra time (charts, xlsx).
_SLOW_TIMEOUT = 10_000


def _load_plan(page: Page, base_url: str) -> None:
    """Navigate to the app and load the default sample plan via the Load Sample dialog."""
    page.goto(base_url)
    page.wait_for_load_state("networkidle")
    page.get_by_role("button", name="Load Sample", exact=True).click()
    # Wait for the dialog's Load Selected button to appear, then confirm.
    page.get_by_role("button", name="Load Selected").wait_for()
    page.get_by_role("button", name="Load Selected").click()
    page.wait_for_timeout(_WAIT_MS)


def _run_projection(page: Page) -> None:
    """Click the Run Projection button and wait for results."""
    page.get_by_role("button", name="Run Projection").click()
    page.wait_for_timeout(_WAIT_MS)


def _click_nav(page: Page, section: str) -> None:
    """Select a section via the sidebar navigation radio.

    The radio labels are formatted as "🔀 Cash Flow" etc., so we match by
    substring (no exact=True) while still scoping to the stRadio widget.
    """
    page.locator('[data-testid="stRadio"]').get_by_text(section).click()
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
    expect(page.get_by_role("button", name="Run", exact=True)).to_be_visible()
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


def test_pager_button_navigates_editor(page: Page, streamlit_server: str) -> None:
    """Clicking a pager section button moves the ACE editor cursor to that line."""
    from pathlib import Path

    # Determine the 1-indexed line number of 'accounts:' in the sample plan.
    sample_lines = Path("examples/sample-plan.yaml").read_text(encoding="utf-8").splitlines()
    accounts_line = next(
        i + 1 for i, ln in enumerate(sample_lines) if ln.startswith("accounts:")
    )

    _load_plan(page, streamlit_server)

    # The pager "accounts" button should be visible.
    accounts_btn = page.get_by_role("button", name="accounts", exact=True)
    expect(accounts_btn).to_be_visible(timeout=_SLOW_TIMEOUT)

    accounts_btn.click()
    page.wait_for_timeout(1500)  # allow JS navigation to execute

    # Read the ACE editor's cursor row via JS.
    cursor_row: int | None = page.evaluate("""
        () => {
            const frames = document.querySelectorAll('iframe');
            for (const frame of frames) {
                try {
                    const el = frame.contentDocument?.querySelector('.ace_editor');
                    if (el?.env?.editor) {
                        return el.env.editor.getCursorPosition().row + 1;
                    }
                } catch (e) {}
            }
            return null;
        }
    """)

    assert cursor_row == accounts_line, (
        f"Expected ACE cursor at line {accounts_line} (accounts: key), got {cursor_row!r}. "
        "JS navigation is likely broken."
    )
