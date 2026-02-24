"""Shared pytest fixtures for the finplanning test suite."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

# Resolve the venv streamlit binary relative to the running interpreter so the
# fixture works regardless of whether the venv is activated.
_VENV_BIN = Path(sys.executable).parent
_STREAMLIT = str(_VENV_BIN / "streamlit")


@pytest.fixture(scope="session")
def streamlit_server() -> str:
    """Launch the Streamlit app on port 8502 and yield the base URL."""
    proc = subprocess.Popen(
        [
            _STREAMLIT,
            "run",
            "streamlit_app.py",
            "--server.headless=true",
            "--server.port=8502",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(4)  # allow Streamlit to boot
    yield "http://localhost:8502"
    proc.terminate()
    proc.wait()
