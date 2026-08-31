import os
import subprocess
from pathlib import Path

import pytest
from docutils import nodes
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needuml import get_debug_node_from_puml_node


def _warnings(app) -> list[str]:
    """Return the build's warnings, with the source directory path normalised away."""
    return strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml"}],
    indirect=True,
)
def test_doc_build_html(test_app, snapshot):
    app = test_app
    app.build()

    assert Path(app.outdir, "index.html").read_text(encoding="utf8")

    data = SphinxNeedsData(app.env)

    all_needs = {k: {**v} for k, v in data.get_needs_view().items()}
    assert all_needs == snapshot()

    all_needumls = data.get_or_create_umls()
    assert all_needumls == snapshot(exclude=props("process_time"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_duplicate_key"}],
    indirect=True,
)
def test_needuml_option_key_duplicate(test_app):
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Inside need: INT_001, "
        "found duplicate Needuml option key name: sequence"
        in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_name_diagram"}],
    indirect=True,
)
def test_needuml_option_key_forbidden(test_app):
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: Needuml option key name can't be: diagram"
        in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_diagram_allowmixing"}],
    indirect=True,
)
def test_needuml_diagram_allowmixing(test_app):
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 0


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_save"}],
    indirect=True,
)
def test_needuml_save(test_app, snapshot):
    app = test_app
    app.build()

    # check generated plantuml code saved in given path
    from sys import platform

    if platform == "win32":
        assert "doc_needuml_save\\_build\\html" in str(app.outdir)
    else:
        assert "doc_needuml_save/_build/html" in str(app.outdir)
    assert app.config.needs_build_needumls == "my_needumls"

    uml_path = Path(app.outdir).joinpath(app.config.needs_build_needumls)
    umls = {
        "uml1": uml_path.joinpath("_build", "my_needuml.puml").read_text(),
        "uml2": uml_path.joinpath("_out", "sub_folder", "my_needs.puml").read_text(),
    }
    assert umls == snapshot


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_save_with_abs_path"}],
    indirect=True,
)
def test_needuml_save_with_abs_path(test_app):
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    # this fails before plantuml is required, so the plantuml path is not provided
    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Given save path: /_out/my_needuml.puml, is not a relative posix path."
        in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needumls", "srcdir": "doc_test/doc_needuml_save"}],
    indirect=True,
)
def test_needumls_builder(test_app, snapshot):
    app = test_app
    app.build()

    # check generated plantuml code saved in given path
    from sys import platform

    if platform == "win32":
        assert "doc_needuml_save\\_build\\needumls" in str(app.outdir)
    else:
        assert "doc_needuml_save/_build/needumls" in str(app.outdir)

    uml_path = Path(app.outdir)
    umls = {
        "uml1": uml_path.joinpath("_build", "my_needuml.puml").read_text(),
        "uml2": uml_path.joinpath("_out", "sub_folder", "my_needs.puml").read_text(),
    }
    assert umls == snapshot


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_filter"}],
    indirect=True,
)
def test_needuml_filter(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "as ST_002 [[../index.html#ST_002]]" in html

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 0


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_jinja_func_flow"}],
    indirect=True,
)
def test_needuml_jinja_func_flow(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "as ST_001 [[../index.html#ST_001]]" in html

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 0


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_jinja_func_need_removed"}],
    indirect=True,
)
def test_needuml_jinja_func_need_removed(test_app):
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1
    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Jinja function 'need()' is not supported in needuml directive."
        in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_jinja_func_import_negative_tests",
        }
    ],
    indirect=True,
)
def test_doc_needarch_jinja_import_negative(test_app):
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )

    assert out.returncode == 1
    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Jinja function 'import()' is not supported in needuml directive."
        in out.stderr.decode("utf-8")
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_jinja_func_ref"}],
    indirect=True,
)
def test_needuml_jinja_func_ref(test_app, snapshot):
    app = test_app
    app.build()

    all_needumls = app.env._needs_all_needumls
    assert all_needumls == snapshot(exclude=props("process_time"))

    html = Path(app.outdir, "index.html").read_text(encoding="utf8")
    assert "Marvel: [[../index.html#ST_001 Test story]]" in html
    assert "DC: [[../index.html#ST_002 Different text to explain the story]]" in html

    assert "Marvel: [[../index.html#ST_001.np_id np_id]]" in html
    assert "DC: [[../index.html#ST_001.np_id np_content]]" in html

    assert (
        "Marvel: [[../index.html#ST_001.np_id Different text to explain the story 2]]"
        in html
    )

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 0


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_option_warnings"}],
    indirect=True,
)
def test_needuml_option_warnings(test_app):
    """A bad ``:config:``, ``:extra:`` or ``:scale:`` value is reported.

    All three were silent before: an unknown config name was dropped without a word,
    a non-numeric scale fell back to 100 without a word, and an ``:extra:`` segment
    carrying no colon ended the whole build with an unhandled ``ValueError``.  A value
    that itself contains a colon must survive, the pair being split on the first colon
    only.
    """
    app = test_app
    app.build()

    assert _warnings(app) == [
        "srcdir/index.rst:4: WARNING: config name 'no_such_config' is not defined in "
        "needs_flow_configs. [needs.needuml]",
        "srcdir/index.rst:4: WARNING: extra option 'broken' is not a 'key:value' pair. "
        "[needs.needuml]",
        'srcdir/index.rst:12: WARNING: scale value must be a number. "not-a-number" '
        "found [needs.diagram_scale]",
    ]

    needuml, scaled = app.env._needs_all_needumls.values()
    assert needuml["extra"] == {"url": "https://example.com/a:b", "plain": "value"}
    assert 'card "https://example.com/a:b" as a' in needuml["content_calculated"]
    assert 'card "value" as b' in needuml["content_calculated"]
    # the known config name is still applied, the unknown one simply skipped
    assert "allowmixing" in needuml["content_calculated"]
    # the unusable scale still falls back to 100 and the diagram is still rendered,
    # the value is only now announced rather than silently discarded
    assert scaled["scale"] == "not-a-number"
    assert 'card "fallback scale" as c' in scaled["content_calculated"]
    assert ".svg" in Path(app.outdir, "index.html").read_text(encoding="utf8")


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_key_missing"}],
    indirect=True,
)
def test_needuml_jinja_func_uml_missing_key(test_app):
    """``uml()`` with an arch key the need does not have names the key and the need.

    The guard subscripted ``arch`` before testing for the key, so the intended message
    was unreachable and the build ended on a bare ``KeyError`` instead.
    """
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1

    stderr = out.stderr.decode("utf-8")
    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Option key name: nosuchkey does not exist in need SP_001." in stderr
    )
    assert "KeyError: 'nosuchkey'" not in stderr


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_import_string_option"}],
    indirect=True,
)
def test_needuml_jinja_func_import_string_option(test_app):
    """``import()`` of an option holding a plain string names the option.

    A string is iterable, so it used to be consumed one character at a time and each
    character looked up as a need id, reporting the first character as an unknown id.
    """
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build"

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1

    stderr = out.stderr.decode("utf-8")
    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Option value for 'status' is not a list of need ids: 'open'." in stderr
    )
    assert "undefined need_id: 'o'" not in stderr


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/doc_needuml_jinja_warnings"}],
    indirect=True,
)
def test_needuml_jinja_func_warnings(test_app):
    """``ref()`` and ``import()`` report what they silently accepted before.

    ``ref()``'s own validation was unreachable (``(a and b) and (not a and not b)``),
    so passing both ``option`` and ``text``, or neither, went unreported; ``import()``
    ignored an option name the need does not carry.  None of them changes what is
    rendered, so all three are warnings rather than errors.
    """
    app = test_app
    app.build()

    assert _warnings(app) == [
        "srcdir/index.rst:13: WARNING: Jinja function ref() was given both 'option' "
        "and 'text' for need_id 'SP_001'; the value of 'option' is used. "
        "[needs.needuml]",
        "srcdir/index.rst:13: WARNING: Jinja function ref() was given neither "
        "'option' nor 'text' for need_id 'SP_001'; the link is rendered without a "
        "label. [needs.needuml]",
        "srcdir/index.rst:13: WARNING: Jinja function import() is called with option "
        "name 'no_such_option', which does not exist in need SP_002. [needs.needuml]",
    ]

    (needuml,) = app.env._needs_all_needumls.values()
    content = needuml["content_calculated"]
    # option wins when both are given, and the label-less link keeps its old shape
    assert "Alice -> Bob: [[../index.html#SP_001 Test spec]]" in content
    assert "Bob --> Alice: [[../index.html#SP_001]]" in content
    assert "Alice -> Bob: [[../index.html#SP_001 only text]]" in content
    # a genuine list of ids is still imported
    assert "as SP_001 [[../index.html#SP_001]]" in content


def test_get_debug_node_from_puml_node_figure():
    """The figure branch of the ``:debug:`` block reads the figure's child.

    The branch assigned from the child and was then unconditionally overwritten by the
    figure's own (absent) ``uml`` attribute, so it could only ever produce an empty
    debug block -- a botched copy of :func:`~sphinx_needs.diagrams_common.
    get_debug_container`, which has the same code written correctly.  Nothing in the
    current pipeline wraps the plantuml node in a figure, hence the direct call.
    """
    child = nodes.Element()
    child["uml"] = "@startuml\nAlice -> Bob: <hi>\n@enduml"
    figure = nodes.figure()
    figure += child

    assert (
        "Alice -&gt; Bob: &lt;hi&gt;" in get_debug_node_from_puml_node(figure).astext()
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needumls", "srcdir": "doc_test/doc_needuml_save"}],
    indirect=True,
)
def test_needumls_builder_rerun_keeps_saved_files(test_app):
    """A second build must not truncate the ``.puml`` files the first one wrote.

    ``content_calculated`` is filled in while a document is written, after the
    environment has been pickled, so a build that re-reads nothing has an empty value
    for every needuml -- which the builder used to write over the good file, leaving
    zero bytes behind.
    """
    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = srcdir / "_build_rerun"
    saved = [
        out_dir / "_build" / "my_needuml.puml",
        out_dir / "_out" / "sub_folder" / "my_needs.puml",
    ]

    first: list[str] = []
    for run in range(2):
        out = subprocess.run(
            ["sphinx-build", "-b", "needumls", str(srcdir), str(out_dir)],
            capture_output=True,
        )
        assert out.returncode == 0, out.stderr.decode("utf-8")

        contents = [path.read_text() for path in saved]
        assert all(content.strip() for content in contents), (
            f"a saved .puml file is empty after run {run + 1}: {contents}"
        )
        if run == 0:
            first = contents
        else:
            assert contents == first


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/doc_needuml_save_no_plantuml",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needuml_save_without_plantuml(test_app):
    """Without PlantUML there is nothing to save, so no file is written.

    The unrendered needuml was skipped but its (empty) content was still handed to the
    builder, which wrote a zero-byte ``.puml`` file over anything already there.
    """
    app = test_app
    app.build()

    assert _warnings(app) == [
        "srcdir/index.rst:4: WARNING: PlantUML is not available, so the diagram was "
        "not rendered. Install 'sphinxcontrib-plantuml' and add it to the "
        "'extensions' list to render it. [needs.needuml]"
    ]

    saved = Path(app.outdir, "my_needumls", "_out", "my_needuml.puml")
    assert not saved.exists(), f"an empty file was written to {saved}"
