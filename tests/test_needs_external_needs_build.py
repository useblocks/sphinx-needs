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


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs_rel_base_path")
def test_external_needs_base_url_relative_path(app, status, warning):
    app.build()

    base_url_path = app.config.needs_external_needs[0]["base_url"]
    assert base_url_path == "../../../doc_needs_external_needs/_build/html"

    html = Path(app.outdir, "index.html").read_text()
    assert (
        '<a class="external_link reference external" '
        'href="../../../doc_needs_external_needs/_build/html/index.html#TEST_01">'
        "EXT_TEST_01: TEST_01 DESCRIPTION</a>" in html
    )
