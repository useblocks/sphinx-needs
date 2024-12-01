import subprocess
from pathlib import Path

import pytest
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData


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

    all_needs = dict(data.get_needs_view())
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

    out = subprocess.run(
        ["sphinx-build", "-M", "html", srcdir, out_dir], capture_output=True
    )
    assert out.returncode == 1

    assert (
        "sphinx_needs.directives.needuml.NeedumlException: "
        "Given save path: /_out/my_needuml.puml, is not a relative path."
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
