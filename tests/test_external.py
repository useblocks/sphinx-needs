from __future__ import annotations

import json
import shutil
from pathlib import Path
from textwrap import dedent

import pytest
from sphinx import version_info
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/external_doc"}],
    indirect=True,
)
def test_external_html(test_app: SphinxTestApp):
    app = test_app
    app.build()
    assert strip_colors(app._warning.getvalue()).strip().splitlines() == [
        "WARNING: External need 'EXT_TEST_03' in 'needs_test_small.json' could not be added: Unknown need type 'ask'. [needs.load_external_need]",
        "WARNING: Unknown keys in external need source 'needs_test_small.json': ['unknown_key'] [needs.unknown_external_keys]",
        "WARNING: Non-string values in extra options of external need source 'needs_test_small.json': ['extra2'] [needs.mistyped_external_values]",
    ]
    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<a class="external_link reference external" href="http://my_company.com/docs/v1/index.html#TEST_02">'
        "EXT_TEST_02</a>" in html
    )

    assert (
        '<p>Test need ref: <a class="external_link reference external"'
        ' href="http://my_company.com/docs/v1/index.html#TEST_01">EXT_TEST_01</a></p>'
        in html
    )


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/external_doc"}],
    indirect=True,
)
def test_external_json(test_app: SphinxTestApp, snapshot):
    app = test_app
    app.build()
    json_data = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


def test_export_import_round_trip(tmp_path: Path, snapshot):
    """Test generating needs in one project and importing them in another."""
    project_path = tmp_path / "project"
    project_path.mkdir()

    srcdir = project_path
    builddir = project_path / "_build"
    if version_info < (7, 2):
        from sphinx.testing.path import path

        srcdir = path(str(srcdir))
        builddir = path(str(builddir))

    # run a build that generates needs
    project_path.joinpath("conf.py").write_text(
        dedent("""\
        version = "1.3"
        extensions = ["sphinx_needs"]
        needs_json_remove_defaults = True
        """),
        "utf8",
    )
    project_path.joinpath("index.rst").write_text(
        dedent("""\
        Title
        =====
               
        .. req:: REQ_01
           :id: REQ_01
        """),
        "utf8",
    )
    app = SphinxTestApp(buildername="needs", srcdir=srcdir, builddir=builddir)
    try:
        app.build()
    finally:
        app.cleanup()
    assert app._warning.getvalue() == ""

    json_data = Path(str(app.outdir), "needs.json").read_bytes()

    # remove previous project
    app.cleanup()
    shutil.rmtree(project_path)
    project_path.mkdir(parents=True, exist_ok=True)
    Path(str(app.outdir)).mkdir(parents=True, exist_ok=True)

    Path(str(app.srcdir), "exported_needs.json").write_bytes(json_data)

    # run a build that exports the generated needs
    project_path.joinpath("conf.py").write_text(
        dedent("""\
        version = "1.3"
        extensions = ["sphinx_needs"]
        needs_id_regex = "^[A-Za-z0-9_]*"
        needs_external_needs = [{
            'json_path':  'exported_needs.json',
            'base_url': 'http://my_company.com/docs/v1/',
            'version': '1.3',
            'id_prefix': 'EXT_',
        }]
        needs_builder_filter = ""
        needs_json_remove_defaults = True
        """),
        "utf8",
    )
    project_path.joinpath("index.rst").write_text(
        dedent("""\
        Title
        =====
  
        .. needimport:: exported_needs.json
            :id_prefix: IMP_

        """),
        "utf8",
    )
    app = SphinxTestApp(buildername="needs", srcdir=srcdir, builddir=builddir)
    try:
        app.build()
    finally:
        app.cleanup()
    assert app._warning.getvalue() == ""

    json_data = json.loads(Path(str(app.outdir), "needs.json").read_text("utf8"))

    assert json_data == snapshot(exclude=props("created", "project", "creator"))
