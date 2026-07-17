import pytest

from imagegen_core import apply_style, discover_style_config


def test_discovers_config_in_parent(tmp_path):
    (tmp_path / "imagegen.toml").write_text(
        '[style]\nprefix = "editorial photo"\nsuffix = "muted palette"\n'
    )
    nested = tmp_path / "src" / "components"
    nested.mkdir(parents=True)
    assert discover_style_config(nested) == {
        "prefix": "editorial photo",
        "suffix": "muted palette",
    }


def test_returns_none_when_absent(tmp_path):
    assert discover_style_config(tmp_path) is None


def test_apply_style_wraps_prompt():
    style = {"prefix": "editorial photo", "suffix": "muted palette"}
    assert (
        apply_style("a pottery studio", style)
        == "editorial photo, a pottery studio, muted palette"
    )


def test_apply_style_none_passthrough():
    assert apply_style("a pottery studio", None) == "a pottery studio"


def test_apply_style_partial():
    assert apply_style("x", {"suffix": "warm light"}) == "x, warm light"


def test_malformed_toml_raises_actionable_error(tmp_path):
    (tmp_path / "imagegen.toml").write_text("[style\nprefix =")
    with pytest.raises(ValueError, match="imagegen.toml"):
        discover_style_config(tmp_path)
