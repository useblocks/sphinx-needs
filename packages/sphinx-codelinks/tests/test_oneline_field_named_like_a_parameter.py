"""A one-line need's field named like a parameter of sphinx-needs' creation call (#2392).

The one-line need's fields used to reach ``add_need`` as keyword arguments, beside its own
parameters: a field named ``state`` (its parser state) ended the build with ``TypeError:
add_need() got multiple values for keyword argument 'state'``. They now go to
``create_need`` as a mapping, where no field name meets a parameter.
"""

from pathlib import Path

from sphinx_needs.data import SphinxNeedsData

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
