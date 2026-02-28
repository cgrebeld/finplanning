# Financial Planning Helper

A long-term financial planning tool for Canadian households. Model income, taxes, investments, and spending across any time horizon.

## Financial Modeling Features (Engine)

- Multi-person household modeling with age-based timelines, life expectancy, and province-aware tax treatment (current tax data support is BC).
- Account-level portfolio modeling across `RRSP`, `RRIF`, `TFSA`, `NON_REGISTERED`, `LIRA`, and `LIF`.
- Asset-mix-based return projection for equity, fixed income, cash, and real estate assumptions.
- Cash-flow projection with recurring income, recurring expenses, one-time events, and recurring periodic expenses.
- Income modeling for employment, self-employment, pension, rental, CPP, OAS, and other sources.
- CPP and OAS benefit modeling with configurable start ages and OAS clawback logic.
- Federal + provincial income tax calculations by year, including projected future tax table indexation.
- Retirement decumulation logic with configurable withdrawal order (e.g., non-registered before registered accounts).
- Registered contribution handling for RRSP and TFSA room constraints when annual surplus is available.
- Pension income splitting optimization (where eligible) to reduce household tax burden.
- Inflation modeling with category-specific effects and healthcare inflation premium.
- Retirement spending falloff/rebound curve support via the Blanchett-style spending decline ("retirement spending smile") assumption.
- Glide-path support for age-based equity-risk reduction over time.
- Black-swan stress test assumptions (equity shock year + flat-return recovery period).
- Scenario planning with base case + override scenarios and side-by-side scenario comparison.
- Monte Carlo simulation with configurable iterations/seed and depletion-risk probability outputs.

## UI Features (High-Level)

- Streamlit web app for loading, editing, and running financial plans from YAML.
- Sample plan browser plus local file upload for custom household plans.
- Built-in YAML editor with section pager/navigation and apply/reload workflow.
- Sidebar controls for scenario selection and projection start/end year ranges.
- One-click projection run with validation/error feedback.
- Overview dashboard with headline metrics (net worth, depletion age, projection length, withdrawal onset).
- Interactive charts including net worth trajectory, gap analysis, tax heatmap, and yearly cash-flow Sankey.
- Year-level drilldown of projected household cash flows and tax components.
- Monte Carlo view with configurable simulation parameters and progress reporting.
- Scenario comparison view for cross-scenario outcome analysis.
- Data export view for downloadable tabular outputs (including Excel export).
- Session-state-driven workflow that preserves loaded plan, scenario, and run results during navigation.

## Requirements

- Python 3.12 (exactly — the bundled wheel requires it)
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

## Install

```bash
uv python install 3.12        # skip if you already have Python 3.12
uv venv --python 3.12
source .venv/bin/activate     # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

This installs Streamlit, Plotly, Pandas, and the bundled `finplanning_core` engine from `wheels/`.

> **Note:** `requirements.txt` and `wheels/` are updated automatically by CI when a new engine release is published. Do not edit `requirements.txt` manually.

## Run

```bash
streamlit run streamlit_app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

## Getting Started

1. Select a plan file from the sidebar (e.g. `examples/sample-plan.yaml`)
2. Click **Load**
3. Click **Run Projection**

Example plans are in the `examples/` directory.
