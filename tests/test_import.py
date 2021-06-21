import json
from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/import_doc")  # , warningiserror=True)
def test_import_json(app, status, warning):
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    assert "TEST IMPORT TITLE" in html
    assert "TEST_01" in html
    assert "test_TEST_01" in html
    assert "new_tag" in html

    # Check filters
    filter_html = Path(app.outdir, "filter.html").read_text()
    assert "TEST_01" not in filter_html
    assert "TEST_02" in filter_html

    # search() test
    assert "AAA" in filter_html

    # :hide: worked
    assert "needs-tag hidden" not in html
    assert "hidden_TEST_01" not in html

    # :collapsed: work
    assert "collapsed_TEST_01" in html


@with_app(buildername="needs", srcdir="doc_test/import_doc")  # , warningiserror=True)
def test_import_builder(app, status, warning):
    app.build()
    needs_text = Path(app.outdir, "needs.json").read_text()
    needs = json.loads(needs_text)
    assert "created" in needs.keys()
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
