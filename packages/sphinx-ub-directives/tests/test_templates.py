"""Template rules the corpus cannot carry: dependencies (§7.11), the Sphinx-only
backstop for a third-party directive that reads a file (§7.10), and ``var`` without
sphinx-needs (§4.6)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sphinx.testing.util import SphinxTestApp

from sphinx_needs_testkit import build_warnings

from .corpus import CONF_PY

DECLARED = """\
[parse.template_contexts.data]
file = "data.json"

[parse.template_contexts.gone]
file = "missing.json"

[parse.directive_templates.row]
template = "_templates/row.rst.j2"

[parse.directive_templates.lost]
template = "_templates/nope.rst.j2"
"""


def _build(
    make_app: Callable[..., SphinxTestApp],
    root: Path,
    files: dict[str, str],
    conf: str = CONF_PY,
) -> SphinxTestApp:
    for relative, text in {"conf.py": conf, **files}.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    app = make_app("html", srcdir=root, freshenv=True)
    app.build()
    return app


def test_every_input_is_a_dependency(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """Every template, context file and include a use reads -- a missing one included --
    is a dependency of the page, so creating or editing it re-reads the page."""
    files = {
        "ubproject.toml": DECLARED.replace(
            '[parse.template_contexts.gone]\nfile = "missing.json"\n', ""
        ),
        "data.json": '{"a": 1}\n',
        "_templates/row.rst.j2": '{% include "_templates/part.j2" %} {{ contexts.data.a }}\n',
        "_templates/part.j2": "part\n",
        "index.rst": "Case\n====\n\n.. row::\n\n.. lost::\n",
    }
    app = _build(make_app, tmp_path, files)
    deps = {
        Path(p).relative_to(tmp_path).as_posix() for p in app.env.dependencies["index"]
    }
    assert {
        "data.json",
        "_templates/row.rst.j2",
        "_templates/part.j2",
        "_templates/nope.rst.j2",
    } <= deps, deps


def test_a_missing_context_file_is_a_dependency(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    files = {
        "ubproject.toml": DECLARED,
        "data.json": '{"a": 1}\n',
        "_templates/row.rst.j2": "{{ contexts.data.a }}\n",
        "index.rst": "Case\n====\n\n.. row::\n",
    }
    app = _build(make_app, tmp_path, files)
    deps = {
        Path(p).relative_to(tmp_path).as_posix() for p in app.env.dependencies["index"]
    }
    assert "missing.json" in deps, deps


def test_a_third_party_directive_noting_a_dependency_is_reported(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§7.10: a directive neither tool's list names, which reads a file in a Sphinx
    build, is the project's responsibility; the Sphinx half says so when it notes a
    dependency while the output is parsed (``template_reads_dependency``)."""
    conf = (
        "import os, sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
        + CONF_PY
        + "extensions = [*extensions, 'reader']\n"
    )
    reader = (
        "from docutils.parsers.rst import Directive\n"
        "class Reader(Directive):\n"
        "    required_arguments = 1\n"
        "    def run(self):\n"
        "        self.state.document.settings.env.note_dependency(self.arguments[0])\n"
        "        return []\n"
        "def setup(app):\n"
        "    app.add_directive('reader', Reader)\n"
    )
    files = {
        "ubproject.toml": '[parse.directive_templates.emit]\nbody = ".. reader:: secret.txt"\n',
        "reader.py": reader,
        "secret.txt": "x\n",
        "index.rst": "Case\n====\n\n.. reader:: own.txt\n\n.. emit::\n",
    }
    app = _build(make_app, tmp_path, files, conf=conf)
    found = [
        w for w in build_warnings(app) if "ub_directives.template_reads_dependency" in w
    ]
    assert len(found) == 1, build_warnings(app)
    assert "secret.txt" in found[0]


def test_var_without_sphinx_needs_is_read_by_ub_project(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    files = {
        "ubproject.toml": '[variants.data]\nedition = "pro"\n\n[parse.directive_templates.ed]\nbody = "Edition {{ var.edition }}."\n',
        "index.rst": "Case\n====\n\n.. ed::\n",
    }
    app = _build(
        make_app, tmp_path, files, conf='extensions = ["sphinx_ub_directives"]\n'
    )
    assert "Edition pro." in (Path(app.outdir) / "index.html").read_text(
        encoding="utf-8"
    )
