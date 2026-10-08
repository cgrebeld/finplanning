import runpy
from pathlib import Path


def test_streamlit_entrypoint_exists_and_loads_run_app() -> None:
    project_root = Path(__file__).resolve().parents[1]
    entrypoint = project_root / "streamlit_app.py"

    assert entrypoint.exists()

    module_globals = runpy.run_path(str(entrypoint), run_name="test_entrypoint")
    run_app = module_globals.get("run_app")
    assert callable(run_app)
