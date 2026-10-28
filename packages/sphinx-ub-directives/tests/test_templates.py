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


def test_a_symlink_out_of_the_root_is_refused(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§2.4 (fix round 1, M8): the clamp is by REAL path, so a context file or a template
    file that is a symlink to outside the source root is refused and never read."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text('{"s": "SECRET"}\n', encoding="utf-8")
    (outside / "secret.rst.j2").write_text("SECRET\n", encoding="utf-8")
    for kind, toml, code in (
        # each build declares its own name: the first app's directives stay registered in
        # docutils until the test ends
        (
            "context",
            '[parse.template_contexts.c]\nfile = "data.json"\n\n[parse.directive_templates.uc]\nbody = "{{ contexts.c.s }}"\n',
            "template_context_invalid",
        ),
        (
            "template",
            '[parse.directive_templates.ut]\ntemplate = "t.rst.j2"\n',
            "template_outside_root",
        ),
    ):
        root = tmp_path / kind
        root.mkdir()
        (root / "data.json").symlink_to(outside / "secret.json")
        (root / "t.rst.j2").symlink_to(outside / "secret.rst.j2")
        name = "uc" if kind == "context" else "ut"
        app = _build(
            make_app,
            root,
            {"ubproject.toml": toml, "index.rst": f"Case\n====\n\n.. {name}::\n"},
        )
        warnings = build_warnings(app)
        assert [w for w in warnings if f"ub_directives.{code}" in w], (kind, warnings)
        assert "SECRET" not in (Path(app.outdir) / "index.html").read_text(
            encoding="utf-8"
        )


def test_a_refused_context_path_is_a_dependency(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§7.11 (M8): a context path outside the root is refused, and still noted."""
    files = {
        "ubproject.toml": '[parse.template_contexts.c]\nfile = "../outside.json"\n\n[parse.directive_templates.u]\nbody = "x"\n',
        "index.rst": "Case\n====\n\n.. u::\n",
    }
    app = _build(make_app, tmp_path / "src", files)
    deps = {Path(p).name for p in app.env.dependencies["index"]}
    assert "outside.json" in deps, deps


def test_a_nul_in_a_template_path_is_refused_not_a_crash(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L1: a NUL in a declared path is a path outside the root, never an exception."""
    files = {
        "ubproject.toml": '[parse.directive_templates.n]\ntemplate = "a\\u0000.rst.j2"\n',
        "index.rst": "Case\n====\n\n.. n::\n",
    }
    app = _build(make_app, tmp_path, files)
    assert [
        w for w in build_warnings(app) if "ub_directives.template_outside_root" in w
    ]


def test_a_localized_name_of_a_reading_directive_is_refused(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§7.10 (H1): with ``language = "de"`` docutils reads ``einfügen`` as ``include``; the
    refusal judges the directive it translates to. (ubCode has no ``language``, so this is
    a test of this package and not a corpus case.)"""
    files = {
        "ubproject.toml": '[parse.directive_templates.emit]\nbody = ".. einfügen:: secret.txt"\n',
        "secret.txt": "SECRET\n",
        "index.rst": "Case\n====\n\n.. emit::\n",
    }
    app = _build(make_app, tmp_path, files, conf=CONF_PY + 'language = "de"\n')
    assert [
        w
        for w in build_warnings(app)
        if "ub_directives.template_output_reads_file" in w
    ]
    assert "SECRET" not in (Path(app.outdir) / "index.html").read_text(encoding="utf-8")


def test_a_syntax_error_names_the_template(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L2 (§1.2): a render error names the template, a syntax error included."""
    files = {
        "ubproject.toml": '[parse.directive_templates.t]\ntemplate = "_t/broken.rst.j2"\n',
        "_t/broken.rst.j2": "ok\n{% for %}\n",
        "index.rst": "Case\n====\n\n.. t::\n",
    }
    app = _build(make_app, tmp_path, files)
    errors = [
        w for w in build_warnings(app) if "ub_directives.template_render_error" in w
    ]
    assert errors and "_t/broken.rst.j2, line 2" in errors[0], errors


def test_a_configuration_finding_is_located_in_ubproject_toml(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L3: a configuration finding names ``ubproject.toml`` and its table's line, not a
    document (Sphinx reads a location without a ``:`` as a document name)."""
    files = {
        "ubproject.toml": '# a comment\n\n[parse.directive_templates.note]\nbody = "x"\n',
        "index.rst": "Case\n====\n",
    }
    app = _build(make_app, tmp_path, files)
    found = [w for w in build_warnings(app) if "directive_template_invalid" in w]
    assert found and found[0].startswith("<srcdir>/ubproject.toml:3: "), found
