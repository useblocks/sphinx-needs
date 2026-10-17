"""A layout's ``{{field}}`` placeholder on a value that is unset or not a string (#2303).

The value was put into the layout function's argument as it was, so an unset field
(``None``) or a number stopped the build with ``TypeError: replace() argument 2 must be
str``. A field declared on one need type alone makes the first the normal case: it holds
``None`` on every other type's needs. A value is now written as its text, a list as its
items joined with ``", "`` (as ``meta`` shows them), and the element built from an unset
or empty value is left out, as ``image("field:...")`` leaves out an image whose field is
unset.
"""

from pathlib import Path

import pytest
from sphinx.application import Sphinx

from sphinx_needs_testkit import build_warnings

LAYOUT = """
needs_layouts = {
    "example": {
        "grid": "simple",
        "layout": {
            "head": ['**<<meta("title")>>**'],
            "meta": [
                '<<link("target_{{value}}", text="value {{value}}")>>'
            ],
        },
    }
}
"""


def project(field: str, option: str, nullable: bool = True) -> dict[str, object]:
    """``test_app`` parameters: one need using the layout, with ``option`` as its value."""
    conf = (
        'extensions = ["sphinx_needs"]\n'
        f"needs_fields = {{'value': {{'schema': {field}, 'nullable': {nullable}"
        + ("" if nullable else ", 'default': ''")
        + "}}\n"
        + LAYOUT
    )
    need = ".. req:: A need\n   :id: REQ_001\n   :layout: example\n" + option
    return {
        "buildername": "html",
        "files": [
            (Path("conf.py"), conf),
            (Path("index.rst"), "Index\n=====\n\n" + need),
        ],
    }


@pytest.mark.parametrize(
    ("test_app", "text"),
    [
        (project("{'type': 'integer'}", "   :value: 3\n"), "3"),
        (project("{'type': 'number'}", "   :value: 1.5\n"), "1.5"),
        (project("{'type': 'boolean'}", "   :value: false\n"), "False"),
        (
            project(
                "{'type': 'array', 'items': {'type': 'string'}}", "   :value: a, b\n"
            ),
            "a, b",
        ),
        (project("{'type': 'string'}", "   :value: plain\n"), "plain"),
    ],
    indirect=["test_app"],
    ids=["integer", "number", "boolean", "array", "string"],
)
def test_placeholder_writes_the_value_as_text(test_app: Sphinx, text: str):
    """A value that is not a string was a ``TypeError``; it is written as its text."""
    test_app.build()
    assert build_warnings(test_app) == []
    html = Path(test_app.outdir, "index.html").read_text()
    assert f'href="target_{text}"' in html
    assert f"value {text}</a>" in html


@pytest.mark.parametrize(
    "test_app",
    [
        project("{'type': 'string'}", ""),
        project("{'type': 'integer'}", ""),
        project("{'type': 'array', 'items': {'type': 'string'}}", "   :value:\n"),
        # not nullable, default "": a need that leaves it unset holds the empty string
        project("{'type': 'string'}", "", nullable=False),
    ],
    indirect=True,
    ids=["unset-string", "unset-integer", "empty-array", "empty-string-default"],
)
def test_placeholder_on_unset_value_leaves_the_element_out(test_app: Sphinx):
    """An unset value was a ``TypeError``; the element built from it is left out."""
    test_app.build()
    assert build_warnings(test_app) == []
    html = Path(test_app.outdir, "index.html").read_text()
    assert "A need" in html
    assert "target_" not in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                (
                    Path("conf.py"),
                    """\
extensions = ["sphinx_needs"]
needs_types = [
    {"directive": "req", "title": "Requirement", "prefix": "R_",
     "fields": {"author": {"schema": {"type": "string"}}}},
    {"directive": "spec", "title": "Specification", "prefix": "S_"},
]
needs_layouts = {
    "example": {
        "grid": "simple_side_right_partial",
        "layout": {
            "head": ['**<<meta("title")>>**'],
            "meta": ['**author**: <<meta("author")>>'],
            "side": ['<<image("_images/{{author}}.png", align="center")>>'],
        },
    }
}
""",
                ),
                (
                    Path("index.rst"),
                    """\
Index
=====

.. spec:: A spec
   :id: SPEC_001
   :layout: example
""",
                ),
            ],
        }
    ],
    indirect=True,
)
def test_image_placeholder_on_field_declared_on_another_type(test_app: Sphinx):
    """The docs' ``example`` layout on a need of a type that does not declare ``author``.

    The field holds ``None`` there, so no image path is built (no ``_images/.png``,
    which would be an unreadable image), and nothing is reported.
    """
    test_app.build()
    assert build_warnings(test_app) == []
    html = Path(test_app.outdir, "index.html").read_text()
    assert "A spec" in html
    assert "<img" not in html
