"""Where a use's needs and findings are reported on the Sphinx side (contract §1.2): at the
directive's own line, in every page and template markup, and after earlier inserted lines.

The corpora compare findings by code, never by line, so these Sphinx-only tests are what
pins the line. Each use's template writes a paragraph with an unknown role two lines in,
and a need four lines in, so a location taken from the rendered text (or the directive
line plus an offset into it) is a different number from the directive's line.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

from .corpus import CONF_PY

TOML = """\
[needs]

[parse]
ub_template_enabled = true

[parse.directive_templates.rowrst]
template = "_templates/row.rst.j2"
argument = { required = true }

[parse.directive_templates.rowmd]
template = "_templates/row.md.j2"
argument = { required = true }

[parse.directive_templates.boom]
body = "{{ nope }}"
"""

#: The same rendered text in each markup: a lead line, an unknown role on line 3, and a
#: need from line 5.
TEMPLATES = {
    "_templates/row.rst.j2": (
        "Lead.\n\nRole :nosuchrole:`x` here.\n\n.. req:: Row\n   :id: {{ argument }}\n"
    ),
    "_templates/row.md.j2": (
        "Lead.\n\nRole {nosuchrole}`x` here.\n\n```{req} Row\n:id: {{ argument }}\n```\n"
    ),
}

RST_PAGE = """\
Case
====

.. toctree::

   mdpage

Padding.

.. rowrst:: RST_IN_RST

More padding.

.. rowmd:: MD_IN_RST
"""

MD_PAGE = """\
# MD page

Padding.

```{rowmd} MD_IN_MD
```

More padding.

```{rowrst} RST_IN_MD
```
"""


def _project(root: Path, files: dict[str, str]) -> Path:
    for relative, text in {"conf.py": CONF_PY, **files}.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
    return root


def _line_of(text: str, marker: str) -> int:
    """The 1-based line of the first line of ``text`` holding ``marker``."""
    return next(n for n, line in enumerate(text.splitlines(), 1) if marker in line)


def _needs(app: SphinxTestApp) -> dict[str, dict[str, object]]:
    data = json.loads((Path(app.outdir) / "needs.json").read_text(encoding="utf-8"))
    return data["versions"][data["current_version"]]["needs"]


@pytest.fixture
def four_ways(make_app: Callable[..., SphinxTestApp], tmp_path: Path) -> SphinxTestApp:
    root = _project(
        tmp_path,
        {
            "ubproject.toml": TOML,
            **TEMPLATES,
            "index.rst": RST_PAGE,
            "mdpage.md": MD_PAGE,
        },
    )
    app = make_app("html", srcdir=root, freshenv=True)
    app.build()
    return app


@pytest.mark.parametrize(
    ("need", "page", "file"),
    [
        pytest.param(
            "RST_IN_RST", RST_PAGE, "index.rst", id="rst-template-in-an-rst-page"
        ),
        pytest.param(
            "MD_IN_RST", RST_PAGE, "index.rst", id="md-template-in-an-rst-page"
        ),
        pytest.param("MD_IN_MD", MD_PAGE, "mdpage.md", id="md-template-in-an-md-page"),
        pytest.param(
            "RST_IN_MD", MD_PAGE, "mdpage.md", id="rst-template-in-an-md-page"
        ),
    ],
)
def test_a_use_reports_at_its_directive_line(
    four_ways: SphinxTestApp, need: str, page: str, file: str
) -> None:
    """L1 (§1.2): the need a use makes, and a warning from parsing its rendered text, are at
    the directive's line in all four page and template combinations -- never the rendered
    text's own line, nor the directive's line plus an offset into the rendered text. The
    warning is a Sphinx warning, reported once (the structural pass reports nothing)."""
    line = _line_of(page, need)
    assert _needs(four_ways)[need]["lineno"] == line
    roles = [w for w in build_warnings(four_ways) if "nosuchrole" in w]
    assert len(roles) == 4, roles
    assert len([w for w in roles if w.startswith(f"<srcdir>/{file}:{line}:")]) == 1, (
        roles
    )


#: Output whose need is inside another directive, which myst and docutils render again
#: with an offset of their own.
NESTED = {
    "_templates/nest.rst.j2": (
        "Lead.\n\n.. note::\n   :class: x\n\n   Inside.\n\n"
        "   .. req:: Nested\n      :id: {{ argument }}\n"
    ),
    "_templates/nest.md.j2": (
        "Lead.\n\n````{note}\n:class: x\n\nInside.\n\n"
        "```{req} Nested\n:id: {{ argument }}\n```\n````\n"
    ),
}

NESTED_TOML = TOML + "".join(
    f'\n[parse.directive_templates.nest{m}]\ntemplate = "_templates/nest.{m}.j2"\n'
    "argument = { required = true }\n"
    for m in ("rst", "md")
)


def test_a_need_nested_in_output_is_at_the_directive_line(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L1: a need inside a directive of the output (a note) is at the use's line too, in
    every combination -- the nested render adds no offset into the rendered text."""
    rst = "Case\n====\n\n.. toctree::\n\n   mdpage\n\n.. nestrst:: N_RST_RST\n\n.. nestmd:: N_MD_RST\n"
    md = "# MD\n\nPadding.\n\n```{nestmd} N_MD_MD\n```\n\n```{nestrst} N_RST_MD\n```\n"
    root = _project(
        tmp_path,
        {"ubproject.toml": NESTED_TOML, **NESTED, "index.rst": rst, "mdpage.md": md},
    )
    app = make_app("html", srcdir=root, freshenv=True)
    app.build()
    needs = _needs(app)
    found = {
        need: needs[need]["lineno"]
        for need in ("N_RST_RST", "N_MD_RST", "N_MD_MD", "N_RST_MD")
    }
    assert found == {
        "N_RST_RST": _line_of(rst, "N_RST_RST"),
        "N_MD_RST": _line_of(rst, "N_MD_RST"),
        "N_MD_MD": _line_of(md, "N_MD_MD"),
        "N_RST_MD": _line_of(md, "N_RST_MD"),
    }


INCLUDED = "".join(f"Included line {n}.\n\n" for n in range(1, 6))


def test_own_warnings_after_an_include_carry_the_real_line(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L2: after an ``include`` has inserted lines, this package's own findings (a render
    error, in a declared template and in ``ub-template``) are at the line written in the
    page, and the inline template's name carries that line; a raw ``self.lineno`` counts
    the inserted lines too."""
    page = (
        "Case\n====\n\n.. include:: five.txt\n\n.. boom::\n\n"
        ".. ub-template::\n\n   {{ undefined_b }}\n"
    )
    root = _project(
        tmp_path, {"ubproject.toml": TOML, "five.txt": INCLUDED, "index.rst": page}
    )
    app = make_app("html", srcdir=root, freshenv=True)
    app.build()
    _assert_own_lines(build_warnings(app), page)


def test_own_warnings_after_a_template_use_carry_the_real_line(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L2: the same after an earlier template use, whose output was inserted into the page:
    the later uses' findings and the inline name are at the line written in the page."""
    page = (
        "Case\n====\n\n.. rowrst:: FIRST\n\n.. boom::\n\n"
        ".. ub-template::\n\n   {{ undefined_b }}\n"
    )
    files = {"ubproject.toml": TOML, **TEMPLATES, "index.rst": page}
    root = _project(tmp_path, files)
    app = make_app("html", srcdir=root, freshenv=True)
    app.build()
    _assert_own_lines(build_warnings(app), page)


def _assert_own_lines(warnings: list[str], page: str) -> None:
    boom, inline = _line_of(page, ".. boom::"), _line_of(page, ".. ub-template::")
    errors = [w for w in warnings if "ub_directives.template_render_error" in w]
    assert [w for w in errors if w.startswith(f"<srcdir>/index.rst:{boom}:")], errors
    assert [
        w
        for w in errors
        if w.startswith(f"<srcdir>/index.rst:{inline}:")
        and re.search(rf"\bindex:{inline}\b", w)
    ], errors
