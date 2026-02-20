"""Edit Plan view — full-width YAML editor and Run Projection button."""

from __future__ import annotations

import streamlit as st

try:
    from streamlit_ace import st_ace
except ImportError:  # pragma: no cover - optional dependency
    st_ace = None

from app.state import apply_yaml_edits, run_projection


def render_edit_plan_view() -> None:
    """Render the full-width YAML editor and Run Projection button."""
    st.header("Edit Plan")

    editor_version = st.session_state.get("editor_version", 0)
    if st_ace is not None:
        yaml_text = st_ace(
            value=st.session_state.get("yaml_editor", ""),
            language="yaml",
            theme="tomorrow_night_bright",
            key=f"yaml_editor_{editor_version}",
            height=560,
            auto_update=False,
            tab_size=2,
            wrap=True,
            show_gutter=True,
            show_print_margin=False,
            font_size=14,
        )
        yaml_text = yaml_text or ""
    else:
        yaml_text = st.text_area(
            "Edit plan YAML",
            value=st.session_state.get("yaml_editor", ""),
            height=560,
            key=f"yaml_editor_{editor_version}",
            label_visibility="collapsed",
        )

    if yaml_text != st.session_state.get("yaml_applied", ""):
        apply_yaml_edits(yaml_text)

    yaml_edit_error: str | None = st.session_state.get("yaml_edit_error")
    if yaml_edit_error:
        st.error(yaml_edit_error)

    if st.button("Run Projection", type="primary"):
        run_projection()
        st.rerun()
