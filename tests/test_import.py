import json
import subprocess
from pathlib import Path

import pytest
import responses
from syrupy.filters import props


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/import_doc"}],
    indirect=True,
)
def test_import_json(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "TEST IMPORT TITLE" in html
    assert "TEST_01" in html
    assert "test_TEST_01" in html
    assert "new_tag" in html

    # Check filters
    filter_html = Path(app.outdir, "subdoc/filter.html").read_text()
    assert "TEST_01" not in filter_html
    assert "TEST_02" in filter_html

    # search() test
    assert "AAA" in filter_html

    # :hide: worked
    assert "needs-tag hidden" not in html
    assert "hidden_TEST_01" not in html

    # :collapsed: work
    assert "collapsed_TEST_01" in html

    # Check absolute path import
    abs_path_import_html = Path(app.outdir, "subdoc/abs_path_import.html").read_text()
    assert "small_abs_path_TEST_02" in abs_path_import_html

    # Check relative path import
    rel_path_import_html = Path(app.outdir, "subdoc/rel_path_import.html").read_text()
    assert "small_rel_path_TEST_01" in rel_path_import_html

    # Check deprecated relative path import based on conf.py
    deprec_rel_path_import_html = Path(
        app.outdir, "subdoc/deprecated_rel_path_import.html"
    ).read_text()
    assert "small_depr_rel_path_TEST_01" in deprec_rel_path_import_html

    warning = app._warning
    warnings = warning.getvalue()
    assert "Deprecation warning:" in warnings


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/import_doc_invalid"}],
    indirect=True,
)
def test_json_schema_console_check(test_app):
    """Checks the console output for hints about json schema validation errors"""
    import os
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = os.path.join(srcdir, "_build")
    out = subprocess.run(
        ["sphinx-build", "-b", "html", srcdir, out_dir], capture_output=True
    )

    assert "Schema validation errors detected" in str(out.stdout)


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/import_doc_invalid"}],
    indirect=True,
)
def test_json_schema_file_check(test_app):
    """Checks that an invalid json-file gets normally still imported and is used as normal (if possible)"""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "TEST_01" in html
    assert "test_TEST_01" in html
    assert "new_tag" in html


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/import_doc_empty"}],
    indirect=True,
)
def test_empty_file_check(test_app):
    """Checks that an empty needs.json throws an exception"""
    app = test_app
    from sphinx_needs.needsfile import SphinxNeedsFileException

    with pytest.raises(SphinxNeedsFileException):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/non_exists_file_import"}],
    indirect=True,
)
def test_import_non_exists_json(test_app):
    # Check non exists file import
    try:
        app = test_app
        app.build()
    except ReferenceError as err:
        assert err.args[0].startswith("Could not load needs import file")
        assert "non_exists_file_import" in err.args[0]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/import_doc"}],
    indirect=True,
)
def test_import_builder(test_app, snapshot):
    app = test_app
    app.build()
    needs_text = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(needs_text)
    assert needs == snapshot(exclude=props("created"))


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/doc_needimport_download_needs_json"}],
    indirect=True,
)
def test_needimport_needs_json_download(test_app, snapshot):
    app = test_app

    # Mock requests
    remote_json = {
        "created": "2022-05-11T13:54:22.331741",
        "current_version": "1.0",
        "project": "needs test docs",
        "versions": {
            "1.0": {
                "created": "2021-05-11T13:54:22.331724",
                "filters": {},
                "filters_amount": 0,
                "needs": {
                    "TEST_101": {
                        "id": "TEST_101",
                        "description": "TEST_101 DESCRIPTION",
                        "docname": "index",
                        "external_css": "external_link",
                        "external_url": "http://my_company.com/docs/v1/index.html#TEST_01",
                        "title": "TEST_101 TITLE",
                        "type": "impl",
                        "tags": ["ext_test"],
                    },
                    "TEST_102": {
                        "id": "TEST_102",
                        "description": "TEST_102 DESCRIPTION",
                        "docname": "index",
                        "external_css": "external_link",
                        "external_url": "http://my_company.com/docs/v1/index.html#TEST_01",
                        "title": "TEST_102 TITLE",
                        "type": "req",
                        "tags": ["ext_test_req"],
                    },
                },
            },
            "2.0": {
                "created": "2022-05-11T13:54:22.331724",
                "filters": {},
                "filters_amount": 0,
                "needs": {
                    "TEST_200": {
                        "id": "TEST_200",
                        "description": "TEST_200 DESCRIPTION",
                        "docname": "index",
                        "external_css": "external_link",
                        "external_url": "http://my_company.com/docs/v1/index.html#TEST_01",
                        "title": "TEST_200 TITLE",
                        "type": "impl",
                        "tags": ["ext_test"],
                    }
                },
            },
        },
    }

    with responses.RequestsMock() as m:
        m.get("http://my_company.com/docs/v1/remote-needs.json", json=remote_json)
        app.build()

    needs_all_needs = app.env.needs_all_needs
    assert needs_all_needs == snapshot(exclude=props("content_node"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_needimport_download_needs_json_negative",
        }
    ],
    indirect=True,
)
def test_needimport_needs_json_download_negative(test_app):
    app = test_app
    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    output = subprocess.run(
        ["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True
    )
    assert (
        "NeedimportException: Getting http://my_wrong_name_company.com/docs/v1/remote-needs.json didn't work."
        in output.stderr.decode("utf-8")
    )
