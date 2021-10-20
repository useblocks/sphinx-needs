from pathlib import Path

from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs")
def test_doc_build_html(app, status, warning):
    import subprocess

    src_dir = "doc_test/doc_needs_external_needs"
    out_dir = Path(app.outdir)
    output = subprocess.run(["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True)
    assert not output.stderr

    # run second time and check
    output_second = subprocess.run(["sphinx-build", "-M", "html", src_dir, out_dir], capture_output=True)
    assert not output_second.stderr
