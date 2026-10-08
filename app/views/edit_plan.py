"""Edit Plan view — YAML editor plus a portfolio profile and equity-region form."""

import logging
import re
from typing import Any

import streamlit as st
import yaml

try:
    from streamlit_ace import st_ace
except ImportError:  # pragma: no cover - optional dependency
    st_ace = None

from ..state import apply_yaml_edits

_TOP_KEY_RE = re.compile(r'^([a-zA-Z_][\w-]*):\s*(?:[^#\n]+?)?\s*(?:#.*)?$')
_LIST_ITEM_RE = re.compile(r'^  - ')
_NAME_4_RE = re.compile(r'^    name:\s*["\']?([^"\'#\n]+?)["\']?\s*(?:#.*)?$')
_NAME_INLINE_RE = re.compile(r'^  - name:\s*["\']?([^"\'#\n]+?)["\']?\s*(?:#.*)?$')
_LOGGER = logging.getLogger(__name__)

PROFILES = ("GLOBAL_CAD_2026_09", "LEGACY_US")
REGIONS = ("CANADA", "US", "DEVELOPED_EX_NA", "EMERGING")
_REGION_LABELS = {"CANADA": "Canada", "US": "US", "DEVELOPED_EX_NA": "Developed ex-NA", "EMERGING": "Emerging"}
# MSCI ACWI as of 2026-09-30: the engine's GLOBAL_CAD_2026_09 default weights.
_DEFAULT_WEIGHTS = {"CANADA": 0.029, "US": 0.6421, "DEVELOPED_EX_NA": 0.2093, "EMERGING": 0.1196}

type Regions = dict[str, float] | None


def _check_regions(where: str, regions: Regions) -> None:
    if regions is None:
        return
    if any(not 0.0 <= weight <= 1.0 for weight in regions.values()):
        raise ValueError(f"{where}: equity region weights must be between 0 and 1")
    if abs(sum(regions.values()) - 1.0) > 0.001:
        raise ValueError(f"{where}: equity region weights sum to {sum(regions.values()):.4f}, not 1")


def apply_portfolio_settings(
    yaml_text: str, profile: str, plan_regions: Regions, account_regions: dict[str, Regions]
) -> str:
    """Return the plan YAML with its market profile and plan/account equity regions set.

    ``account_regions`` lists every account override; other accounts use the plan weights. Global
    profiles drop ``canadian_equity_share`` (LEGACY_US only; the CANADA weight replaces it).
    LEGACY_US drops regional weights, which it rejects. Raises ValueError for weights not summing to 1.
    """
    if profile not in PROFILES:
        raise ValueError(f"Unknown portfolio profile {profile!r}")
    legacy = profile == "LEGACY_US"
    if not legacy:
        _check_regions("Plan", plan_regions)
        for account_id, regions in account_regions.items():
            _check_regions(f"Account {account_id}", regions)
    raw = yaml.safe_load(yaml_text)
    portfolio = raw.setdefault("assumptions", {}).get("portfolio") or {}
    portfolio["profile"] = profile
    portfolio.pop("equity_regions", None)
    if plan_regions is not None and not legacy:
        portfolio["equity_regions"] = {region: weight for region, weight in plan_regions.items() if weight}
    raw["assumptions"]["portfolio"] = portfolio
    for account in raw.get("accounts") or []:
        account.pop("equity_regions", None)
        if legacy:
            continue
        account.pop("canadian_equity_share", None)
        regions = account_regions.get(account.get("id"))
        if regions is not None:
            account["equity_regions"] = {region: weight for region, weight in regions.items() if weight}
    return yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)


def _region_inputs(key: str, current: dict[str, Any] | None) -> dict[str, float]:
    weights = {region: float((current or _DEFAULT_WEIGHTS).get(region, 0.0)) for region in REGIONS}
    cols = st.columns(len(REGIONS))
    values = {
        region: col.number_input(
            _REGION_LABELS[region], 0.0, 1.0, weights[region], 0.01, format="%.4f", key=f"{key}_{region}"
        )
        for region, col in zip(REGIONS, cols, strict=True)
    }
    st.caption(f"Sum {sum(values.values()):.4f} (must be 1)")
    return values


def _render_portfolio_form(yaml_text: str, editor_version: int) -> None:
    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return
    if not isinstance(raw, dict):
        return
    portfolio = (raw.get("assumptions") or {}).get("portfolio") or {}
    equity_accounts = [
        a for a in raw.get("accounts") or [] if isinstance(a, dict) and (a.get("asset_mix") or {}).get("equity")
    ]
    key = f"portfolio_{editor_version}"
    with st.expander("Portfolio profile and equity regions"):
        current = portfolio.get("profile", PROFILES[0])
        profile = st.selectbox(
            "Market profile",
            PROFILES,
            index=PROFILES.index(current) if current in PROFILES else 0,
            key=f"{key}_profile",
            help="GLOBAL_CAD_2026_09: CAD returns 1991-2025 for four equity regions (unhedged), Canadian bonds "
            "and T-bills. LEGACY_US: the pre-0.18 US-only history, which needs canadian_equity_share on "
            "taxable equity accounts instead of regions.",
        )
        plan_regions: Regions = None
        account_regions: dict[str, Regions] = {}
        if profile == "LEGACY_US":
            st.caption("LEGACY_US uses one equity series; regional weights are removed on apply.")
        else:
            if st.checkbox(
                "Set plan equity weights (otherwise MSCI ACWI 2026-09-30)",
                value=portfolio.get("equity_regions") is not None,
                key=f"{key}_plan",
            ):
                plan_regions = _region_inputs(f"{key}_plan", portfolio.get("equity_regions"))
            for account in equity_accounts:
                account_id = account.get("id")
                if st.checkbox(
                    f"Override equity weights for {account_id}",
                    value=account.get("equity_regions") is not None,
                    key=f"{key}_acct_{account_id}",
                ):
                    account_regions[account_id] = _region_inputs(
                        f"{key}_acct_{account_id}", account.get("equity_regions") or plan_regions
                    )
            st.caption("canadian_equity_share is LEGACY_US only and is removed on apply.")
        st.caption("Applying rewrites the YAML and drops its comments.")
        if st.button("Apply portfolio settings", key=f"{key}_apply"):
            try:
                new_text = apply_portfolio_settings(yaml_text, profile, plan_regions, account_regions)
            except ValueError as exc:
                st.error(str(exc))
                return
            apply_yaml_edits(new_text)
            if st.session_state.get("yaml_edit_error"):  # the engine rejected it; keep the editor as is
                st.error(st.session_state["yaml_edit_error"])
                return
            st.session_state["editor_version"] = editor_version + 1
            st.rerun()


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
  console.info('[yaml-pager] nav script start', {{ line: line }});

  function findEditorInDocument(doc) {{
    if (!doc) return null;
    var el = doc.querySelector('.ace_editor');
    if (el && el.env && el.env.editor) return el.env.editor;
    return null;
  }}

  function tryNav() {{
    var editor = findEditorInDocument(window.document);
    if (editor) {{
      console.info('[yaml-pager] found editor in current document', {{ line: line }});
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
    }} catch (e) {{
      console.warn('[yaml-pager] parent iframe access failed', e);
    }}

    console.debug('[yaml-pager] scanning iframes', {{ count: frames.length, retry: retries }});

    for (var i = 0; i < frames.length; i++) {{
      try {{
        var win = frames[i].contentWindow;
        editor = findEditorInDocument(win && win.document ? win.document : null);
        if (editor) {{
          console.info('[yaml-pager] found editor in iframe', {{ index: i, line: line }});
          editor.gotoLine(line, 0, true);
          editor.focus();
          return;
        }}
      }} catch (e) {{
        console.debug('[yaml-pager] iframe scan failed', {{ index: i, error: String(e) }});
      }}
    }}

    if (++retries < 30) {{
      setTimeout(tryNav, 100);
      return;
    }}
    console.error('[yaml-pager] editor not found after retries', {{ retries: retries, line: line }});
  }}

  tryNav();
}})({target_line});
</script>"""


def render_edit_plan_view() -> None:
    """Render the YAML editor with a left-side section pager."""
    st.header("Edit Plan")

    yaml_text_for_pager = st.session_state.get("yaml_editor", "")
    _render_portfolio_form(yaml_text_for_pager, st.session_state.get("editor_version", 0))
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
                        width="stretch",
                        help=f"line {key_line}",
                        type="tertiary",
                    ):
                        _LOGGER.info("yaml-pager click key=%s target_line=%s", key_name, key_line)
                        st.session_state["pager_target_line"] = key_line
                    for child_name, child_line in children:
                        if st.button(
                            f"↳ {child_name}",
                            key=f"pager_child_{key_name}_{child_line}",
                            width="stretch",
                            help=f"line {child_line}",
                            type="tertiary",
                        ):
                            _LOGGER.info(
                                "yaml-pager click child=%s parent=%s target_line=%s",
                                child_name,
                                key_name,
                                child_line,
                            )
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
        _LOGGER.info("yaml-pager inject-nav-script target_line=%s", target_line)
        st.html(
            _build_ace_nav_script(target_line),
            unsafe_allow_javascript=True,
        )
    elif target_line is not None:
        _LOGGER.info("yaml-pager fallback-textarea target_line=%s", target_line)
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
