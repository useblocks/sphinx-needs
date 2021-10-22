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

    # check if incremental build used
    # first build output
    assert "making output directory" in output.stdout.decode("utf-8")
    assert "updating environment: [new config] 1 added, 0 changed, 0 removed" in output.stdout.decode("utf-8")
    # second build output
    assert "making output directory" not in output_second.stdout.decode("utf-8")
    assert "loading pickled environment" in output_second.stdout.decode("utf-8")
    assert "updating environment: [new config] 1 added, 0 changed, 0 removed" not in output_second.stdout.decode(
        "utf-8"
    )
    assert "updating environment: 0 added, 0 changed, 0 removed" in output_second.stdout.decode("utf-8")
