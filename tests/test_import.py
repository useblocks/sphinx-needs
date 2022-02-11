import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/import_doc"}], indirect=True)
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
    deprec_rel_path_import_html = Path(app.outdir, "subdoc/deprecated_rel_path_import.html").read_text()
    assert "small_depr_rel_path_TEST_01" in deprec_rel_path_import_html

    warning = app._warning
    warnings = warning.getvalue()
    assert "Deprecation warning:" in warnings


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/import_doc_invalid"}], indirect=True)
def test_json_schema_console_check(test_app):
    """Checks the console output for hints about json schema validation errors"""
    import os
    import subprocess

    app = test_app

    srcdir = Path(app.srcdir)
    out_dir = os.path.join(srcdir, "_build")
    out = subprocess.run(["sphinx-build", "-b", "html", srcdir, out_dir], capture_output=True)

    assert "Schema validation errors detected" in str(out.stdout)


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/import_doc_invalid"}], indirect=True)
def test_json_schema_file_check(test_app):
    """Checks that an invalid json-file gets normally still imported and is used as normal (if possible)"""
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "TEST_01" in html
    assert "test_TEST_01" in html
    assert "new_tag" in html


@pytest.mark.parametrize(
    "test_app", [{"buildername": "html", "srcdir": "doc_test/non_exists_file_import"}], indirect=True
)
def test_import_non_exists_json(test_app):
    # Check non exists file import
    try:
        app = test_app
        app.build()
    except ReferenceError as err:
        assert err.args[0].startswith("Could not load needs import file")
        assert "non_exists_file_import" in err.args[0]


@pytest.mark.parametrize("test_app", [{"buildername": "needs", "srcdir": "doc_test/import_doc"}], indirect=True)
def test_import_builder(test_app):
    app = test_app
    app.build()
    needs_text = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(needs_text)
    assert "created" in needs
    need = needs["versions"]["1.0"]["needs"]["REQ_1"]

    check_keys = [
        "id",
        "type",
        "description",
        "full_title",
        "is_need",
        "is_part",
        "links",
        "section_name",
        "status",
        "tags",
        "title",
        "type_name",
    ]

    for key in check_keys:
        if key not in need.keys():
            raise AssertionError("%s not in exported need" % key)
