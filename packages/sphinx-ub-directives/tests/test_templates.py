"""Template rules the corpus cannot carry: dependencies (§7.11), the Sphinx-only
backstop for a third-party directive that reads a file (§7.10), and ``var`` without
sphinx-needs (§4.6)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp

from sphinx_needs.data import SphinxNeedsData
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
        path.write_text(text, encoding="utf-8", newline="")
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
    (outside / "secret.json").write_text(
        '{"s": "SECRET"}\n', encoding="utf-8", newline=""
    )
    (outside / "secret.rst.j2").write_text("SECRET\n", encoding="utf-8", newline="")
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


def test_a_context_file_that_is_not_toml_is_refused_with_the_parsers_words(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§4.3: a ``.toml`` context file that does not parse is
    ``template_context_invalid``, and the message is the file's name and the parser's
    own text -- no reader's wrapping in between."""
    files = {
        "ubproject.toml": '[parse.template_contexts.c]\nfile = "c.toml"\n\n[parse.directive_templates.d]\nbody = "{{ contexts.c.a }}"\n',
        "c.toml": "[c\n",
        "index.rst": "Case\n====\n\n.. d::\n",
    }
    app = _build(make_app, tmp_path, files)
    found = [
        w for w in build_warnings(app) if "ub_directives.template_context_invalid" in w
    ]
    assert len(found) == 1, build_warnings(app)
    assert (
        "the context 'c' cannot be used: c.toml is not valid TOML (Expected ']' at the"
        " end of a table declaration (at line 1, column 3))"
    ) in found[0], found


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


def test_an_edited_context_file_is_read_again(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """L9 (fix round 2): the parsed-file memo is keyed by CONTENT, so an edit that keeps
    the file's size and modification time is still seen by the next build of the process."""
    import os

    files = {
        "ubproject.toml": '[parse.template_contexts.c]\nfile = "c.json"\n\n[parse.directive_templates.u]\nbody = "Value {{ contexts.c.v }}."\n',
        "c.json": '{"v": "AAAA"}\n',
        "index.rst": "Case\n====\n\n.. u::\n",
    }
    first = _build(make_app, tmp_path, files)
    assert "Value AAAA." in (Path(first.outdir) / "index.html").read_text(
        encoding="utf-8"
    )
    data = tmp_path / "c.json"
    stat = data.stat()
    data.write_text('{"v": "CCCC"}\n', encoding="utf-8", newline="")
    os.utime(data, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    second = make_app("html", srcdir=tmp_path, freshenv=True)
    second.build()
    assert "Value CCCC." in (Path(second.outdir) / "index.html").read_text(
        encoding="utf-8"
    )


def test_the_inert_parse_reports_nothing(
    make_app: Callable[..., SphinxTestApp],
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """N8: the structural pass (§7.8) parses every output with a reporter that discards,
    so a docutils problem in the output is reported once, by the real parse, and the
    throwaway parse prints nothing (docutils' own reporter would write to stderr)."""
    files = {
        "ubproject.toml": '[parse.directive_templates.u]\nbody = "* An item\\nNot separated by a blank line."\n',
        "index.rst": "Case\n====\n\n.. u::\n",
    }
    app = _build(make_app, tmp_path, files)
    found = [w for w in build_warnings(app) if "unexpected unindent" in w]
    assert len(found) == 1, build_warnings(app)
    assert "unexpected unindent" not in capfd.readouterr().err


def test_the_configured_test_report_names_are_refused(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """N10 (§7.10): with sphinx-test-reports loaded, the names it is CONFIGURED to register
    are the ones refused in output."""
    conf = (
        CONF_PY
        + "extensions = [*extensions, 'sphinx_test_reports']\n"
        + "tr_file = ['my-file', 'myfile', 'My-File', 'MF_', '#ffffff', 'node']\n"
    )
    files = {
        "ubproject.toml": '[parse.directive_templates.u]\nbody = ".. my-file:: Report\\n   :file: r.xml\\n   :id: MF_001"\n',
        "r.xml": '<testsuite name="s" tests="0"></testsuite>\n',
        "index.rst": "Case\n====\n\n.. u::\n",
    }
    app = _build(make_app, tmp_path, files, conf=conf)
    assert [
        w
        for w in build_warnings(app)
        if "ub_directives.template_output_reads_file" in w
    ], build_warnings(app)


def test_a_preset_default_argument_is_a_file_for_a_diagram(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """N11 (§7.10): a preset of graphviz whose default ARGUMENT names a file is refused in
    output, although the use writes no argument."""
    conf = CONF_PY + "extensions = [*extensions, 'sphinx.ext.graphviz']\n"
    files = {
        "ubproject.toml": (
            '[parse.directive_presets.gvarg]\nbase = "graphviz"\nargument = "d.dot"\n\n'
            '[parse.directive_templates.u]\nbody = ".. gvarg::"\n'
        ),
        "d.dot": "digraph { A -> B }\n",
        "index.rst": "Case\n====\n\n.. u::\n",
    }
    app = _build(make_app, tmp_path, files, conf=conf)
    assert [
        w
        for w in build_warnings(app)
        if "ub_directives.template_output_reads_file" in w
    ], build_warnings(app)


def test_a_dot_dot_after_a_missing_component_is_missing_on_every_platform(
    tmp_path: Path,
) -> None:
    """§2.4: a ``..`` applies only after a component that exists as a directory. Windows
    folds ``missing/..`` away lexically, so the rule is decided by walking the components,
    not by the OS: the name is a missing file wherever the build runs."""
    from sphinx_ub_directives._engine import Root

    (tmp_path / "sub").mkdir()
    (tmp_path / "t.j2").write_text("ok", encoding="utf-8", newline="")
    (tmp_path / "f.txt").write_text("x", encoding="utf-8", newline="")
    root = Root(tmp_path)
    for name in ("nope/../t.j2", "f.txt/../t.j2", "sub/nope/../../t.j2"):
        path = root.resolve(name)
        assert path is not None and path in root.missing, name
        with pytest.raises(FileNotFoundError):
            root.read(path)
    for name in ("sub/../t.j2", "./sub/../t.j2", "/sub/../t.j2"):
        path = root.resolve(name)
        assert path is not None and path not in root.missing, name
        assert root.read(path) == "ok"
    assert root.resolve("sub/../../outside.j2") is None


def test_a_need_template_option_in_any_case_in_myst_output_is_refused(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """§7.10: the need directive matches its options ignoring case, and MyST keeps the
    written case, so a ``:Template:`` in MyST output reads a file exactly as
    ``:template:`` does, and is refused the same way (RST output is lower-cased by docutils
    before it is judged; the corpus writes no RST option name with capitals)."""
    files = {
        "ubproject.toml": (
            '[parse.directive_templates.emit]\ntemplate = "_templates/emit.md.j2"\n'
        ),
        "_templates/emit.md.j2": "```{req} R\n:id: REQ_TCAP\n:Template: custom\n```\n",
        "index.md": "# Case\n\n```{emit}\n```\n",
    }
    app = _build(make_app, tmp_path, files)
    refused = [
        w
        for w in build_warnings(app)
        if "ub_directives.template_output_reads_file" in w
    ]
    assert len(refused) == 1, build_warnings(app)


def test_a_need_in_rst_output_on_a_myst_page_has_the_rst_doctype(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path
) -> None:
    """A need's ``doctype`` is the markup its content is written in (sphinx-needs): a
    need in the reStructuredText output of a template used on a MyST page is ``.rst``,
    as one inside ``{eval-rst}`` is; one written on the page is ``.md``."""
    files = {
        "ubproject.toml": (
            "[needs]\n\n"
            "[parse.directive_templates.emitrst]\n"
            'body = ".. req:: From an RST template\\n   :id: REQ_TRST\\n\\n'
            '   RST `l <https://x.example>`_ body.\\n"\n'
            'markup = "rst"\n'
        ),
        "index.md": (
            "# Case\n\n```{emitrst}\n```\n\n```{req} On the page\n:id: REQ_PAGE\n```\n"
        ),
    }
    app = _build(make_app, tmp_path, files)
    assert build_warnings(app) == []
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert needs["REQ_TRST"]["doctype"] == ".rst"
    assert needs["REQ_PAGE"]["doctype"] == ".md"


# -- ``length`` / ``count`` of an undefined value (§7.1) --------------------------------

# Every input the engine's own ``length`` takes, and some it refuses. minijinja-py hands a
# Python filter ``none`` and an undefined value alike as ``None``, a lazy sequence as a
# list and a function as its name, so these pin that the page still gets the ENGINE's
# answer: the render's strict probe only ever refuses, it never measures for the page.
LENGTH_INPUTS = [
    "'abc'",
    "''",
    "'é😀ü'",
    "'a<b>'|safe",
    "'<b>'|escape",
    "[1, 2, 3]",
    "[]",
    "(1, 2)",
    "()",
    "{'a': 1, 'b': 2}",
    "{}",
    "range(5)",
    "[1, -2]|map('abs')",
    "[1, 2, 3]|select('odd')",
    "{'a': 1}|items",
    "'a b c'|split",
    "namespace(a=1, b=2)",
    "[[1], [2]]|map('length')",
    # refused by the engine as well
    "none",
    "1",
    "true",
    "range",
    "joiner()",
]


@pytest.mark.parametrize("name", ["length", "count"])
@pytest.mark.parametrize("value", LENGTH_INPUTS)
def test_length_renders_what_the_engine_renders(
    tmp_path: Path, value: str, name: str
) -> None:
    """Every input but an undefined value gives the engine's own ``length`` byte for
    byte, or fails where it fails."""
    from sphinx_ub_directives._engine import Failure, Root, environment, render

    source = f"[{{{{ ({value})|{name} }}}}]"
    try:
        expected: str | None = environment(Root(tmp_path)).render_str(source)
    except Exception:
        # the engine refuses it, so the render must too
        expected = None
    if expected is None:
        with pytest.raises(Failure) as failure:
            render(source, "t", {}, Root(tmp_path))
        assert failure.value.code == "template_render_error"
    else:
        assert render(source, "t", {}, Root(tmp_path)).text == expected


def test_a_loop_and_a_macro_measure_as_the_engine_measures(tmp_path: Path) -> None:
    """The two engine objects minijinja-py hands a Python filter as a dict, of a size of
    its own, render the engine's numbers."""
    from sphinx_ub_directives._engine import Root, environment, render

    source = (
        "{% macro m(a) %}{% endmacro %}"
        "{% for x in [1, 2] %}{{ loop|length }} {% endfor %}{{ m|length }}"
    )
    expected = environment(Root(tmp_path)).render_str(source)
    assert render(source, "t", {}, Root(tmp_path)).text == expected


@pytest.mark.parametrize(
    "source",
    [
        "{{ nope|length }}",
        "{{ nope|count }}",
        "{% if nope|length %}y{% endif %}n",
        "{% set r = {} %}{{ r.missing|length }}",
        "{{ [{}]|map(attribute='missing')|map('count')|list }}",
        "{% for x in [1] %}{% if loop.missing|length %}{% endif %}{% endfor %}",
    ],
)
def test_length_of_an_undefined_value_is_a_render_error(
    tmp_path: Path, source: str
) -> None:
    """§7.1's strict undefined: minijinja-py 3.1.0's own ``length`` and ``count`` make an
    undefined value ``0``, where minijinja (ubCode's engine) and minijinja-py 3.0.5
    refuse it."""
    from sphinx_ub_directives._engine import Failure, Root, render

    with pytest.raises(Failure) as failure:
        render(source, "t", {}, Root(tmp_path))
    assert failure.value.code == "template_render_error"
    assert "undefined value" in failure.value.message


def test_length_of_an_undefined_value_in_an_include_is_a_render_error(
    tmp_path: Path,
) -> None:
    """The probe renders the same sources: an included template that measures an
    undefined value is refused too, and no file is read twice."""
    from sphinx_ub_directives._engine import Failure, Root, render

    (tmp_path / "inc.j2").write_text("{{ nope|length }}", encoding="utf-8")
    root = Root(tmp_path)
    with pytest.raises(Failure) as failure:
        render("{% include 'inc.j2' %}", "t", {}, root)
    assert failure.value.code == "template_render_error"
    assert root.reads == [tmp_path / "inc.j2"]
