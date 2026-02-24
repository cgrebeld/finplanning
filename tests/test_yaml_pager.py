"""Tests for the YAML pager outline parser and editor navigation helpers."""

from app.views.edit_plan import _build_ace_nav_script, _parse_yaml_outline


def test_empty_string_returns_empty_list():
    assert _parse_yaml_outline("") == []


def test_single_scalar_key():
    yaml = "schema_version: 1\n"
    result = _parse_yaml_outline(yaml)
    assert len(result) == 1
    key, line, children = result[0]
    assert key == "schema_version"
    assert line == 1
    assert children == []


def test_list_key_with_named_children():
    yaml = (
        "accounts:\n"
        "  - id: acc1\n"
        "    name: Savings Account\n"
        "  - id: acc2\n"
        "    name: Investment Account\n"
    )
    result = _parse_yaml_outline(yaml)
    assert len(result) == 1
    key, line, children = result[0]
    assert key == "accounts"
    assert line == 1
    assert len(children) == 2
    assert children[0] == ("Savings Account", 2)
    assert children[1] == ("Investment Account", 4)


def test_list_items_without_name_are_excluded():
    yaml = (
        "withdrawal_order:\n"
        "  - NON_REGISTERED\n"
        "  - RRSP\n"
        "  - TFSA\n"
    )
    result = _parse_yaml_outline(yaml)
    key, line, children = result[0]
    assert children == []


def test_multiple_top_level_keys():
    yaml = (
        "schema_version: 1\n"
        "household:\n"
        "  id: hh1\n"
        "  name: Smith Family\n"
        "accounts:\n"
        "  - id: acc1\n"
        "    name: TFSA\n"
    )
    result = _parse_yaml_outline(yaml)
    keys = [r[0] for r in result]
    assert keys == ["schema_version", "household", "accounts"]


def test_name_with_double_quoted_value():
    yaml = (
        "accounts:\n"
        '  - id: rrsp\n'
        '    name: "Questrade RRSP"\n'
    )
    result = _parse_yaml_outline(yaml)
    _, _, children = result[0]
    assert children[0][0] == "Questrade RRSP"


def test_name_with_single_quoted_value():
    yaml = (
        "scenarios:\n"
        "  - id: base\n"
        "    name: 'Base Case'\n"
    )
    result = _parse_yaml_outline(yaml)
    _, _, children = result[0]
    assert children[0][0] == "Base Case"


def test_line_numbers_are_1_indexed():
    yaml = "accounts:\n  - id: h1\n    name: My Account\n"
    result = _parse_yaml_outline(yaml)
    _, key_line, children = result[0]
    assert key_line == 1
    child_name, child_line = children[0]
    assert child_name == "My Account"
    assert child_line == 2  # the "  - id:" line is the item start


def test_comment_lines_not_treated_as_keys():
    yaml = (
        "# this is a comment\n"
        "accounts:\n"
        "  - name: My Account\n"
    )
    result = _parse_yaml_outline(yaml)
    assert len(result) == 1
    assert result[0][0] == "accounts"


def test_inline_list_item_with_name_field():
    """  - name: Foo  (name is right on the dash line)"""
    yaml = (
        "scenarios:\n"
        "  - name: Base Case\n"
        "    id: base\n"
    )
    result = _parse_yaml_outline(yaml)
    _, _, children = result[0]
    assert children[0][0] == "Base Case"


def test_never_raises_on_garbage_input():
    result = _parse_yaml_outline(":::invalid::\n  - - -\n\t\tbad indent")
    assert isinstance(result, list)


def test_hyphenated_top_level_key():
    yaml = "scenario-overrides:\n  early-retire:\n    equity: 0.05\n"
    result = _parse_yaml_outline(yaml)
    assert len(result) == 1
    assert result[0][0] == "scenario-overrides"
    assert result[0][2] == []  # no named children (no list items with name:)


def test_ace_nav_script_guards_parent_document_access():
    script = _build_ace_nav_script(12)
    assert "window.document.querySelectorAll('iframe')" in script
    assert "window.parent.document.querySelectorAll('iframe')" in script
    assert "try {" in script
    assert "[yaml-pager]" in script
    assert "editor not found after retries" in script
