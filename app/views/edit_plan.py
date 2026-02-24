"""Edit Plan view — full-width YAML editor."""

import re

import streamlit as st

try:
    from streamlit_ace import st_ace
except ImportError:  # pragma: no cover - optional dependency
    st_ace = None

from ..state import apply_yaml_edits

_TOP_KEY_RE = re.compile(r'^([a-zA-Z_][\w-]*):\s*(?:[^#\n]+?)?\s*(?:#.*)?$')
_LIST_ITEM_RE = re.compile(r'^  - ')
_NAME_4_RE = re.compile(r'^    name:\s*["\']?([^"\'#\n]+?)["\']?\s*(?:#.*)?$')
_NAME_INLINE_RE = re.compile(r'^  - name:\s*["\']?([^"\'#\n]+?)["\']?\s*(?:#.*)?$')


def _parse_yaml_outline(
    text: str,
) -> list[tuple[str, int, list[tuple[str, int]]]]:
    """Scan YAML text and return a lightweight outline for the pager.

    Returns [(key_name, line_num, [(child_name, child_line_num), ...]), ...].
    Line numbers are 1-indexed.  Never raises.
    """
    if not text:
        return []

    outline: list[tuple[str, int, list[tuple[str, int]]]] = []
    current_key: str | None = None
    current_key_line: int = 0
    current_children: list[tuple[str, int]] = []
    current_item_line: int | None = None
    current_item_name: str | None = None

    def _flush_item() -> None:
        nonlocal current_item_line, current_item_name
        if current_item_name is not None and current_item_line is not None:
            current_children.append((current_item_name, current_item_line))
        current_item_line = None
        current_item_name = None

    def _flush_key() -> None:
        nonlocal current_key, current_key_line, current_children
        if current_key is not None:
            _flush_item()
            outline.append((current_key, current_key_line, list(current_children)))
        current_key = None
        current_key_line = 0
        current_children.clear()

    try:
        for i, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.rstrip()
            if not line or line.lstrip().startswith('#'):
                continue

            top_m = _TOP_KEY_RE.match(line)
            if top_m:
                _flush_key()
                current_key = top_m.group(1)
                current_key_line = i
                continue

            if current_key is None:
                continue

            inline_m = _NAME_INLINE_RE.match(line)
            if inline_m:
                _flush_item()
                current_item_line = i
                current_item_name = inline_m.group(1).strip()
                continue

            if _LIST_ITEM_RE.match(line):
                _flush_item()
                current_item_line = i
                continue

            name_m = _NAME_4_RE.match(line)
            if name_m and current_item_line is not None:
                current_item_name = name_m.group(1).strip()

    except Exception:  # noqa: BLE001
        pass

    _flush_key()
    return outline


def _build_ace_nav_script(target_line: int) -> str:
    """Build the ACE navigation script with cross-origin-safe document access."""
    return f"""<script>
(function(line) {{
  var retries = 0;

  function findEditorInDocument(doc) {{
    if (!doc) return null;
    var el = doc.querySelector('.ace_editor');
    if (el && el.env && el.env.editor) return el.env.editor;
    return null;
  }}

  function tryNav() {{
    var editor = findEditorInDocument(window.document);
    if (editor) {{
      editor.gotoLine(line, 0, true);
      editor.focus();
      return;
    }}

    var frames = [];
    try {{
      frames = frames.concat(Array.from(window.document.querySelectorAll('iframe')));
    }} catch (e) {{}}
    try {{
      if (window.parent && window.parent !== window) {{
        frames = frames.concat(Array.from(window.parent.document.querySelectorAll('iframe')));
      }}
    }} catch (e) {{}}

    for (var i = 0; i < frames.length; i++) {{
      try {{
        var win = frames[i].contentWindow;
        editor = findEditorInDocument(win && win.document ? win.document : null);
        if (editor) {{
          editor.gotoLine(line, 0, true);
          editor.focus();
          return;
        }}
      }} catch (e) {{}}
    }}

    if (++retries < 30) setTimeout(tryNav, 100);
  }}

  tryNav();
}})({target_line});
</script>"""


def render_edit_plan_view() -> None:
    """Render the YAML editor with a left-side section pager."""
    st.header("Edit Plan")

    yaml_text_for_pager = st.session_state.get("yaml_editor", "")
    outline = _parse_yaml_outline(yaml_text_for_pager)

    col_pager, col_editor = st.columns([1, 4])

    # ── Pager ──────────────────────────────────────────────────────────────
    with col_pager:
        if outline:
            with st.container(height=560, border=False):
                for key_name, key_line, children in outline:
                    if st.button(
                        key_name,
                        key=f"pager_key_{key_name}_{key_line}",
                        use_container_width=True,
                        help=f"line {key_line}",
                        type="tertiary",
                    ):
                        st.session_state["pager_target_line"] = key_line
                    for child_name, child_line in children:
                        if st.button(
                            f"↳ {child_name}",
                            key=f"pager_child_{key_name}_{child_line}",
                            use_container_width=True,
                            help=f"line {child_line}",
                            type="tertiary",
                        ):
                            st.session_state["pager_target_line"] = child_line

    # ── Editor ─────────────────────────────────────────────────────────────
    editor_version = st.session_state.get("editor_version", 0)
    with col_editor:
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

    # ── JS cursor navigation (ACE only) ────────────────────────────────────
    target_line: int | None = st.session_state.pop("pager_target_line", None)
    if not isinstance(target_line, int):
        target_line = None
    if target_line is not None and st_ace is not None:
        st.html(
            _build_ace_nav_script(target_line),
            unsafe_allow_javascript=True,
        )
    elif target_line is not None:
        # st.text_area fallback: show a line-number hint
        st.caption(f"↑ Line {target_line}")

    # ── Apply edits ────────────────────────────────────────────────────────
    if yaml_text != st.session_state.get("yaml_applied", ""):
        apply_yaml_edits(yaml_text)
    else:
        st.session_state["yaml_edit_error"] = None

    yaml_edit_error: str | None = st.session_state.get("yaml_edit_error")
    if yaml_edit_error:
        st.error(yaml_edit_error)
