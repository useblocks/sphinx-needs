from sphinx_testing import with_app


@with_app(buildername="html", srcdir="doc_test/custom_tr_template")
def test_custom_template(app, status, warning):
    app.build()
    html = (app.outdir / "index.html").read_text()

    # assert changed order when creating a testreport html page
    pos1 = html.index("<strong>Imported data</strong>")
    pos2 = html.index('<div class="line">Test suites:')

    assert pos1 < pos2
