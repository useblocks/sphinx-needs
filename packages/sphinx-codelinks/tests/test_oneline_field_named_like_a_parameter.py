"""A one-line need's field named like a parameter of sphinx-needs' creation call (#2392).

The one-line need's fields used to reach ``add_need`` as keyword arguments, beside its own
parameters: a field named ``state`` (its parser state) ended the build with ``TypeError:
add_need() got multiple values for keyword argument 'state'``. They now go to
``create_need`` as a mapping, where no field name meets a parameter.
"""

import hashlib
from pathlib import Path

import pytest

from sphinx_codelinks.sphinx_extension.directives.src_trace import would_be_id
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


def test_a_one_line_field_named_jinja_content_renders_the_content(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``jinja_content`` is an argument of the creation too: the marker's value as
    written, as ``add_need`` recorded it, rendering the content."""
    _project(
        tmp_path,
        toml_extra=(
            "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
            'needs_fields = [{ name = "title" }, { name = "id" }, { name = "content" }, '
            '{ name = "jinja_content" }, { name = "type", default = "impl" }]\n'
        ),
        files={
            "src/impl.cpp": "// @first impl, IMPL_1, of {{ title }}, true\nvoid impl() {}\n"
        },
    )
    app = _build(tmp_path, make_app)
    need = SphinxNeedsData(app.env).get_needs_view()["IMPL_1"]
    assert (need["content"], need["jinja_content"]) == ("of first impl", "true")


def _hashed(prefix: str, text: str) -> str:
    return prefix + hashlib.sha1(text.encode()).hexdigest().upper()[:5]


def _impl_needs(app):
    """The fixture's one-line needs (its pages hold needs of their own)."""
    return {
        need_id: need
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
        if need["type"] == "impl"
    }


def _full_title_style(declared: bool) -> dict[str, str]:
    return {
        "toml_extra": (
            "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
            'needs_fields = [{ name = "title" }, { name = "full_title" }, '
            '{ name = "type", default = "impl" }]\n'
        ),
        "append": (
            {"docs/conf.py": 'needs_fields = {"full_title": {"nullable": True}}\n'}
            if declared
            else {}
        ),
    }


@pytest.mark.xfail(strict=True, reason="FR7: a generated id does not move")
def test_a_declared_full_title_is_the_field_and_the_id_s_full_title(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """With no id, the need's id is hashed from the marker's ``full_title``, as
    ``add_need`` took it, and is the id :func:`would_be_id` predicts (the duplicate
    check and the ``[docs]`` link use it); a declared ``full_title`` also holds it."""
    style = _full_title_style(declared=True)
    _project(
        tmp_path,
        toml_extra=style["toml_extra"],
        files={"src/impl.cpp": "// @first impl, A much longer title\nvoid impl() {}\n"},
        append=style["append"],
    )
    app = _build(tmp_path, make_app)
    needs = _impl_needs(app)
    expected = _hashed("I_", "A much longer title")
    predicted = would_be_id(
        app,
        {"type": "impl", "title": "first impl", "full_title": "A much longer title"},
    )
    assert (list(needs), predicted) == ([expected], expected)
    assert needs[expected]["full_title"] == "A much longer title"


def test_an_undeclared_full_title_is_the_id_s_full_title(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    style = _full_title_style(declared=False)
    _project(
        tmp_path,
        toml_extra=style["toml_extra"],
        files={"src/impl.cpp": "// @first impl, A much longer title\nvoid impl() {}\n"},
    )
    app = _build(tmp_path, make_app)
    assert list(_impl_needs(app)) == [_hashed("I_", "A much longer title")]


def test_a_one_line_field_named_doctype_sets_it(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    _project(
        tmp_path,
        toml_extra=_style("doctype"),
        files={"src/impl.cpp": "// @first impl, IMPL_1, .md\nvoid impl() {}\n"},
    )
    app = _build(tmp_path, make_app)
    assert SphinxNeedsData(app.env).get_needs_view()["IMPL_1"]["doctype"] == ".md"


@pytest.mark.xfail(strict=True, reason="FR8: allow_type_coercion is an argument")
def test_a_one_line_field_named_allow_type_coercion_is_the_argument(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """Undeclared, it is the creation's argument, as ``add_need`` took it: the need is
    built."""
    _project(
        tmp_path,
        toml_extra=_style("allow_type_coercion"),
        files={"src/impl.cpp": "// @first impl, IMPL_1, yes\nvoid impl() {}\n"},
    )
    app = _build(tmp_path, make_app)
    assert "IMPL_1" in SphinxNeedsData(app.env).get_needs_view()
