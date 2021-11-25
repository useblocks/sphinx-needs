import json
from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="needs", srcdir="doc_test/doc_needs_builder")
def test_doc_needs_builder(app, status, warning):
    app.build()

    needs_json = Path(app.outdir, "needs.json")
    with open(needs_json) as needs_file:
        needs_file_content = needs_file.read()

    needs_list = json.loads(needs_file_content)
    assert needs_list["versions"]["1.0"]
    assert needs_list["versions"]["1.0"]["needs"]["TC_NEG_001"]

    # needs builder added new version needs from needs_files
    assert needs_list["versions"]["2.0"]
    assert needs_list["versions"]["2.0"]["needs"]["TEST_01"]


@with_app(buildername="needs", srcdir="doc_test/doc_needs_builder_negative_tests")
def test_doc_needs_build_without_needs_file(app, status, warning):
    import os
    import subprocess

    srcdir = "doc_test/doc_needs_builder_negative_tests"
    out_dir = os.path.join(srcdir, "_build")

    out = subprocess.run(["sphinx-build", "-b", "needs", srcdir, out_dir], capture_output=True)
    assert not out.stderr
    assert "needs.json found, but will not be used because needs_file not configured." in out.stdout.decode("utf-8")


@with_app(buildername="needs", srcdir="../docs")
def test_needs_official_doc(app, status, warning):
    app.build()
