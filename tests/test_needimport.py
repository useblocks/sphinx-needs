import json
import os
from pathlib import Path

import pytest
import responses
from sphinx.util.console import strip_colors
from syrupy.filters import props

from sphinx_needs.data import SphinxNeedsData
from sphinx_needs.directives.needimport import NeedimportException
from sphinx_needs.needsfile import SphinxNeedsFileException


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/import_doc", "no_plantuml": True}],
    indirect=True,
)
def test_import_json(test_app):
    app = test_app
    app.build()
    warnings = app._warning.getvalue()
    warnings_list = strip_colors(
        warnings.replace(str(app.srcdir) + os.sep + "subdoc" + os.sep, "srcdir/subdoc/")
    ).splitlines()

    if os.name != "nt":
        assert warnings_list == [
            "srcdir/subdoc/deprecated_rel_path_import.rst:6: WARNING: Deprecation warning: Relative path must be relative to the current document in future, not to the conf.py location. Use a starting '/', like '/needs.json', to make the path relative to conf.py. [needs.deprecated]"
        ]
    else:
        assert "Deprecation" in warnings

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


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/import_doc_invalid",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_json_schema_check(test_app):
    """Checks that an invalid json-file gets normally still imported and is used as normal (if possible)"""
    test_app.build()
    assert test_app._warning.getvalue() == ""
    assert "Schema validation errors detected" in test_app._status.getvalue()
    html = Path(test_app.outdir, "index.html").read_text()
    assert "TEST_01" in html
    assert "test_TEST_01" in html
    assert "new_tag" in html


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/import_doc_warnings",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_need_schema_warnings(test_app, snapshot):
    """Test warnings are emitted when there are schema validation issues of individual needs."""
    test_app.build()
    warnings = strip_colors(
        test_app._warning.getvalue().replace(str(test_app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
        "srcdir/index.rst:4: WARNING: Unknown keys in import need source: ['unknown_key'] [needs.unknown_import_keys]",
        "srcdir/index.rst:4: WARNING: Non-string values in extra options of import need source: ['extra2'] [needs.mistyped_import_values]",
    ]
    json_data = Path(test_app.outdir, "needs.json").read_text()
    needs = json.loads(json_data)
    assert needs == snapshot(
        exclude=props("created", "project", "creator", "needs_schema")
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/import_doc_empty",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_empty_file_check(test_app):
    """Checks that an empty needs.json throws an exception"""
    app = test_app

    with pytest.raises(SphinxNeedsFileException):
        app.build()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "html",
            "srcdir": "doc_test/non_exists_file_import",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_import_non_exists_json(test_app):
    # Check non exists file import
    app = test_app
    with pytest.raises(ReferenceError) as err:
        app.build()

    assert err.value.args[0].startswith("Could not load needs import file")
    assert "non_exists_file_import" in err.value.args[0]


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "needs", "srcdir": "doc_test/import_doc", "no_plantuml": True}],
    indirect=True,
)
def test_import_builder(test_app, snapshot):
    app = test_app
    app.build()
    needs_text = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(needs_text)
    assert needs == snapshot(exclude=props("created", "project", "creator"))


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_needimport_download_needs_json",
            "no_plantuml": True,
        }
    ],
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

    needs_all_needs = dict(SphinxNeedsData(app.env).get_needs_view())
    assert needs_all_needs == snapshot()


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "needs",
            "srcdir": "doc_test/doc_needimport_download_needs_json_negative",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_needimport_needs_json_download_negative(test_app):
    with pytest.raises(NeedimportException) as err:
        test_app.build()
    assert (
        "Getting http://my_wrong_name_company.com/docs/v1/remote-needs.json didn't work."
        in err.value.args[0]
    )


@pytest.mark.parametrize(
    "test_app",
    [
        {
            "buildername": "latex",
            "srcdir": "doc_test/doc_needimport_noindex",
            "no_plantuml": True,
        }
    ],
    indirect=True,
)
def test_doc_needimport_noindex(test_app):
    app = test_app
    app.build()
    warnings = strip_colors(
        app._warning.getvalue().replace(str(app.srcdir) + os.sep, "srcdir/")
    ).splitlines()
    assert warnings == [
        "srcdir/needimport.rst:6: WARNING: Need 'TEST_01' has unknown outgoing link 'SPEC_1' in field 'links' [needs.link_outgoing]"
    ]

    latex_path = str(Path(app.outdir, "needstestdocs.tex"))
    latex = Path(latex_path).read_text()

    assert Path(latex_path).exists()
    assert len(latex) > 0
    assert "AAA" in latex
