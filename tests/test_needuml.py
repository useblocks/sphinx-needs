import os
import subprocess
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData


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
    """An unknown ``:config:`` name and a malformed ``:extra:`` segment are reported.

    Both were silent before: an unknown config name was dropped without a word, and an
    ``:extra:`` segment carrying no colon ended the whole build with an unhandled
    ``ValueError``.  A value that itself contains a colon must survive, the pair being
    split on the first colon only.
    """
    app = test_app
    app.build()

    assert _warnings(app) == [
        "srcdir/index.rst:4: WARNING: config name 'no_such_config' is not defined in "
        "needs_flow_configs. [needs.needuml]",
        "srcdir/index.rst:4: WARNING: extra option 'broken' is not a 'key:value' pair. "
        "[needs.needuml]",
    ]

    (needuml,) = app.env._needs_all_needumls.values()
    assert needuml["extra"] == {"url": "https://example.com/a:b", "plain": "value"}
    assert 'card "https://example.com/a:b" as a' in needuml["content_calculated"]
    assert 'card "value" as b' in needuml["content_calculated"]
    # the known config name is still applied, the unknown one simply skipped
    assert "allowmixing" in needuml["content_calculated"]


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
