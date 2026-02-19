"""Shared pytest fixtures for the finplanning test suite."""

from __future__ import annotations

import subprocess
import time

import pytest


@pytest.fixture(scope="session")
def streamlit_server():
    """Launch the Streamlit app on port 8502 and yield the base URL."""
    proc = subprocess.Popen(
        [
            "streamlit",
            "run",
            "app/main.py",
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
