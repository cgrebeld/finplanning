# Financial Planning Helper

A long-term financial planning tool for Canadian households. Model income, taxes, investments, and spending across any time horizon.

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
streamlit run app/main.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

## Getting Started

1. Select a plan file from the sidebar (e.g. `examples/sample-plan.yaml`)
2. Click **Load**
3. Click **Run Projection**

Example plans are in the `examples/` directory.
