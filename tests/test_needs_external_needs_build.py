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


@with_app(buildername="html", srcdir="doc_test/doc_needs_external_needs")
def test_external_needs_base_url_relative_path(app, status, warning):
    app.build()

    html = Path(app.outdir, "index.html").read_text()

    # check base_url full path
    base_url_full_path = app.config.needs_external_needs[0]["base_url"]
    assert base_url_full_path == "http://my_company.com/docs/v1"

    assert (
        '<a class="external_link reference external" '
        'href="http://my_company.com/docs/v1/index.html#TEST_01">'
        "EXT_TEST_01: TEST_01 DESCRIPTION</a>" in html
    )

    # check base_url relative path
    base_url_rel_path = app.config.needs_external_needs[1]["base_url"]
    assert base_url_rel_path == "../../_build/html"

    assert (
        '<a class="external_link reference external" '
        'href="../../_build/html/index.html#TEST_01">'
        "EXT_REL_PATH_TEST_01: TEST_01 DESCRIPTION</a>" in html
    )
