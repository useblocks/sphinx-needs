"""A one-line need's field named like a parameter of sphinx-needs' creation call (#2392).

The one-line need's fields used to reach ``add_need`` as keyword arguments, beside its own
parameters: a field named ``state`` (its parser state) ended the build with ``TypeError:
add_need() got multiple values for keyword argument 'state'``. They now go to
``create_need`` as a mapping, where no field name meets a parameter.
"""

from pathlib import Path

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import _build, _MakeApp, _project

STYLE = (
    "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
    'needs_fields = [{ name = "title" }, { name = "id" }, { name = "state" }, '
    '{ name = "app" }, { name = "type", default = "impl" }]\n'
)


def test_a_one_line_field_named_like_a_parameter_is_an_ordinary_field(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _project(
        tmp_path,
        toml_extra=STYLE,
        files={"src/impl.cpp": "// @first impl, IMPL_1, draft, mine\nvoid impl() {}\n"},
        append={
            "docs/conf.py": (
                'needs_fields = {"state": {"nullable": True}, "app": {"nullable": True}}\n'
            )
        },
    )
    app = _build(tmp_path, make_app)
    need = SphinxNeedsData(app.env).get_needs_view()["IMPL_1"]
    assert (need["state"], need["app"]) == ("draft", "mine")


def _style(name: str) -> str:
    return (
        "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
        'needs_fields = [{ name = "title" }, { name = "id" }, '
        f'{{ name = "{name}" }}, {{ name = "type", default = "impl" }}]\n'
    )


def test_a_one_line_field_named_content_sets_the_content(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``content`` is no field but an argument of the creation: a marker field of that
    name is the need's content, as ``add_need`` took it."""
    _project(
        tmp_path,
        toml_extra=_style("content"),
        files={
            "src/impl.cpp": "// @first impl, IMPL_1, the body text\nvoid impl() {}\n"
        },
    )
    app = _build(tmp_path, make_app)
    assert SphinxNeedsData(app.env).get_needs_view()["IMPL_1"]["content"] == (
        "the body text"
    )


def test_a_one_line_field_named_like_a_core_field_no_marker_sets_refuses_the_need(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """A Sphinx-Needs core field that is neither a field nor an argument of the
    creation (``external_url``) refuses the marker's need, with the one-line warning."""
    _project(
        tmp_path,
        toml_extra=_style("external_url"),
        files={
            "src/impl.cpp": "// @first impl, IMPL_1, http://x.org\nvoid impl() {}\n"
        },
    )
    app = _build(tmp_path, make_app)
    assert "IMPL_1" not in SphinxNeedsData(app.env).get_needs_view()
    assert any(
        "one-line need could not be created: {'external_url'} not in 'needs_fields'"
        in warning
        for warning in build_warnings(app)
    )
