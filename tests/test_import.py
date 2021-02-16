import json
import sys
from pathlib import Path

from sphinx_testing import with_app


def read_text(path: Path) -> str:
    if sys.version_info <= (3, 5):
        path = str(path)
    with open(path) as f:
        return f.read()


@with_app(buildername="html", srcdir="doc_test/import_doc")
def test_import_json(app, status, warning):
    app.build()

    html = read_text(Path(app.outdir, "index.html"))

    assert "TEST IMPORT TITLE" in html
    assert "TEST_01" in html
    assert "test_TEST_01" in html
    assert "new_tag" in html

    # Check hidden
    assert "needs-tag hidden" not in html
    assert "Test for XY" not in html

    # Check filters
    filter_html = Path(app.outdir, "filter.html").read_text()
    assert "TEST_01" not in filter_html
    assert "TEST_02" in filter_html

    # search() test
    assert "AAA" in filter_html


@with_app(buildername="needs", srcdir="doc_test/import_doc")
def test_import_builder(app, status, warning):
    app.build()
    json_text = read_text(Path(app.outdir, "needs.json"))
    needs = json.loads(json_text)

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
