from sphinx_testing import with_app


@with_app(buildername='html', srcdir='../docs')
def test_build_html(app, status, warning):
    app.builder.build_all()


@with_app(buildername='singlehtml', srcdir='../docs')
def test_build_singlehtml(app, status, warning):
    app.builder.build_all()


@with_app(buildername='latex', srcdir='../docs')
def test_build_latex(app, status, warning):
    app.builder.build_all()


@with_app(buildername='epub', srcdir='../docs')
def test_build_epub(app, status, warning):
    app.builder.build_all()


@with_app(buildername='json', srcdir='../docs')
def test_build_json(app, status, warning):
    app.builder.build_all()