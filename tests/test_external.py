from __future__ import annotations

import json
import os
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
    warnings = (
        strip_colors(app._warning.getvalue())
        .replace(str(app.srcdir) + os.path.sep, "<srcdir>/")
        .splitlines()
    )
    # print(warnings)
    assert warnings == [
        "WARNING: External need 'EXT_TEST_01' in 'needs_test_small.json' could not be added: Field 'extra2' is invalid: Invalid value for field 'extra2': 1 [needs.load_external_need]",
        "WARNING: External need 'EXT_TEST_03' in 'needs_test_small.json' could not be added: Unknown need type 'ask'. [needs.load_external_need]",
        "WARNING: Unknown keys in external need source 'needs_test_small.json': ['unknown_key'] [needs.unknown_external_keys]",
        "WARNING: http://my_company.com/docs/v1/index.html#TEST_02: Need 'EXT_TEST_02' has unknown outgoing link 'EXT_TEST_01' in field 'links' [needs.external_link_outgoing]",
        "WARNING: http://my_company.com/docs/v1/index.html#TEST_02: Need 'EXT_TEST_02' has unknown outgoing link 'EXT_TEST_01' in field 'parent_needs' [needs.external_link_outgoing]",
        "<srcdir>/index.rst:12: WARNING: Need 'SPEC_1' has unknown outgoing link 'EXT_TEST_01' in field 'links' [needs.link_outgoing]",
        "<srcdir>/index.rst:26: WARNING: linked need EXT_TEST_01 not found [needs.link_ref]",
    ]
    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<a class="external_link reference external" href="http://my_company.com/docs/v1/index.html#TEST_02">'
        "EXT_TEST_02</a>" in html
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


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                ("index.rst", "Test\n====\n"),
                (
                    "conf.py",
                    """
extensions = ["sphinx_needs"]
needs_external_needs = [{
    'json_path':  'needs.json',
    'base_url': 'http://my_company.com/docs/v1/',
    'allow_type_coercion': True,
}]
needs_build_json = True
needs_builder_filter = ''
                 """,
                ),
            ],
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_external_allow_type_coercion_true(test_app):
    """Test allow_type_coercion option for external needs configuration."""
    # write the parametrized index.rst content
    json_path = Path(test_app.srcdir) / "needs.json"
    json_path.write_text(
        json.dumps(
            {
                "current_version": "1",
                "versions": {
                    "1": {
                        "needs": {
                            "TEST_01": {
                                "id": "TEST_01",
                                "title": "TEST IMPORT TITLE",
                                "type": "impl",
                                "tags": "a,b,c",
                            }
                        },
                    }
                },
            }
        )
    )

    app = test_app
    app.build()
    assert app.statuscode == 0
    assert not app._warning.getvalue()

    needs_json = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(needs_json)
    assert needs["versions"][""]["needs"]["TEST_01"]["tags"] == ["a", "b", "c"]


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "files": [
                ("index.rst", "Test\n====\n"),
                (
                    "conf.py",
                    """
extensions = ["sphinx_needs"]
needs_external_needs = [{
    'json_path':  'needs.json',
    'base_url': 'http://my_company.com/docs/v1/',
    'allow_type_coercion': False,
}]
needs_build_json = True
needs_builder_filter = ''
                 """,
                ),
            ],
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_external_allow_type_coercion_false(test_app):
    """Test allow_type_coercion option for external needs configuration."""
    # write the parametrized index.rst content
    json_path = Path(test_app.srcdir) / "needs.json"
    json_path.write_text(
        json.dumps(
            {
                "current_version": "1",
                "versions": {
                    "1": {
                        "needs": {
                            "TEST_01": {
                                "id": "TEST_01",
                                "title": "TEST IMPORT TITLE",
                                "type": "impl",
                                "tags": "a,b,c",
                            }
                        },
                    }
                },
            }
        )
    )

    app = test_app
    app.build()
    assert app.statuscode == 0
    assert strip_colors(app._warning.getvalue()).splitlines() == [
        "WARNING: External need 'TEST_01' in 'needs.json' could not be added: 'tags' value is invalid: Invalid value for field 'tags': 'a,b,c' [needs.load_external_need]"
    ]
