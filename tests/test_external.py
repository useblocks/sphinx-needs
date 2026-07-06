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
}]
needs_build_json = True
                 """,
                ),
            ],
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_external_empty_versions(test_app):
    """Test external needs when the loaded needs.json has an empty versions dict."""
    json_path = Path(test_app.srcdir) / "needs.json"
    json_path.write_text(
        json.dumps(
            {
                "current_version": "0.1.0",
                "project": "foo",
                "project_url": "https://bar",
                "versions": {},
            }
        )
    )

    app = test_app
    app.build()
    assert app.statuscode == 0
    assert not app._warning.getvalue()

    needs_json = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(needs_json)
    # the empty external needs should just be ignored without crashing.
    assert "TEST_01" not in needs["versions"][""]["needs"]


def test_external_sources_provenance_chain(tmp_path: Path):
    """Test that external_sources metadata is written to needs.json and inherited transitively.

    Chain: Project X (origin) -> Project A (consumes X) -> Project B (consumes A)
    Project B should see both A and X in its external_sources.
    """
    if version_info < (7, 2):
        pytest.skip("Requires Sphinx >= 7.2")

    # --- Project X: origin project that just has some needs ---
    project_x = tmp_path / "project_x"
    project_x.mkdir()
    project_x.joinpath("conf.py").write_text(
        dedent("""\
        version = "1.0"
        extensions = ["sphinx_needs"]
        needs_json_remove_defaults = True
        """),
        "utf8",
    )
    project_x.joinpath("index.rst").write_text(
        dedent("""\
        Project X
        =========

        .. req:: Requirement from X
           :id: X_REQ_01
        """),
        "utf8",
    )
    app_x = SphinxTestApp(
        buildername="needs", srcdir=project_x, builddir=project_x / "_build"
    )
    try:
        app_x.build()
    finally:
        app_x.cleanup()
    assert app_x._warning.getvalue() == ""
    x_needs_json = Path(str(app_x.outdir), "needs.json").read_bytes()

    # --- Project A: consumes X, exports including external needs ---
    project_a = tmp_path / "project_a"
    project_a.mkdir()
    project_a.joinpath("x_needs.json").write_bytes(x_needs_json)
    project_a.joinpath("conf.py").write_text(
        dedent("""\
        version = "2.0"
        extensions = ["sphinx_needs"]
        needs_id_regex = "^[A-Za-z0-9_]*"
        needs_external_needs = [{
            'json_path': 'x_needs.json',
            'base_url': 'https://project-x.io/en/latest',
            'version': '1.0',
            'id_prefix': 'PX_',
        }]
        needs_builder_filter = ""
        needs_json_remove_defaults = True
        """),
        "utf8",
    )
    project_a.joinpath("index.rst").write_text(
        dedent("""\
        Project A
        =========

        .. req:: Requirement from A
           :id: A_REQ_01
        """),
        "utf8",
    )
    app_a = SphinxTestApp(
        buildername="needs", srcdir=project_a, builddir=project_a / "_build"
    )
    try:
        app_a.build()
    finally:
        app_a.cleanup()
    assert app_a._warning.getvalue() == ""

    a_json_path = Path(str(app_a.outdir), "needs.json")
    a_needs_data = json.loads(a_json_path.read_text("utf8"))

    # Verify Project A's needs.json has external_sources
    a_version_data = a_needs_data["versions"]["2.0"]
    assert "external_sources" in a_version_data
    a_sources = a_version_data["external_sources"]
    assert len(a_sources) == 1
    assert a_sources[0]["base_url"] == "https://project-x.io/en/latest"
    assert a_sources[0]["origin"] is None  # direct source
    assert a_sources[0]["id_prefix"] == "PX_"

    # Verify the external need has external_source field
    px_req = a_version_data["needs"]["PX_X_REQ_01"]
    assert px_req["is_external"] is True
    assert px_req["external_source"] == "https://project-x.io/en/latest"

    # --- Project B: consumes A, should inherit X's provenance ---
    project_b = tmp_path / "project_b"
    project_b.mkdir()
    project_b.joinpath("a_needs.json").write_bytes(a_json_path.read_bytes())
    project_b.joinpath("conf.py").write_text(
        dedent("""\
        version = "3.0"
        extensions = ["sphinx_needs"]
        needs_id_regex = "^[A-Za-z0-9_]*"
        needs_external_needs = [{
            'json_path': 'a_needs.json',
            'base_url': 'https://project-a.io/en/latest',
            'version': '2.0',
            'id_prefix': 'PA_',
        }]
        needs_builder_filter = ""
        needs_json_remove_defaults = True
        """),
        "utf8",
    )
    project_b.joinpath("index.rst").write_text(
        dedent("""\
        Project B
        =========

        .. req:: Requirement from B
           :id: B_REQ_01
        """),
        "utf8",
    )
    app_b = SphinxTestApp(
        buildername="needs", srcdir=project_b, builddir=project_b / "_build"
    )
    try:
        app_b.build()
    finally:
        app_b.cleanup()
    assert app_b._warning.getvalue() == ""

    b_json_path = Path(str(app_b.outdir), "needs.json")
    b_needs_data = json.loads(b_json_path.read_text("utf8"))

    # Verify Project B's needs.json has both direct and inherited sources
    b_version_data = b_needs_data["versions"]["3.0"]
    assert "external_sources" in b_version_data
    b_sources = b_version_data["external_sources"]
    b_sources_by_url = {s["base_url"]: s for s in b_sources}

    # Direct source: Project A
    assert "https://project-a.io/en/latest" in b_sources_by_url
    assert b_sources_by_url["https://project-a.io/en/latest"]["origin"] is None

    # Inherited source: Project X (via A)
    assert "https://project-x.io/en/latest" in b_sources_by_url
    assert (
        b_sources_by_url["https://project-x.io/en/latest"]["origin"]
        == "https://project-a.io/en/latest"
    )

    # Verify external needs from A have external_source pointing to A
    pa_a_req = b_version_data["needs"]["PA_A_REQ_01"]
    assert pa_a_req["is_external"] is True
    assert pa_a_req["external_source"] == "https://project-a.io/en/latest"

    pa_px_req = b_version_data["needs"]["PA_PX_X_REQ_01"]
    assert pa_px_req["is_external"] is True
    assert pa_px_req["external_source"] == "https://project-a.io/en/latest"
