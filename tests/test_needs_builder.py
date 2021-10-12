import json
from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="needs", srcdir="doc_test/doc_needs_builder")
def test_doc_needs_builder(app, status, warning):
    app.build()

    needs_json = Path(app.outdir, "needs.json")
    with open(needs_json, "r") as needs_file:
        needs_file_content = needs_file.read()

    needs_list = json.loads(needs_file_content)
    # needs builder added new version needs from needs_files
    assert needs_list["versions"]["2.0"]
    assert needs_list["versions"]["2.0"]["needs"]["TEST_01"]


@with_app(buildername="needs", srcdir="doc_test/doc_needs_builder/negative_tests")
def test_doc_needs_build_without_needs_file(app, status, warning):
    app.build()

    # stdout warnings
    warnings = warning.getvalue()
    assert "WARNING: Could not load needs json file" not in warnings
