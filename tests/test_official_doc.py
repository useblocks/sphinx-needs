from nose.tools import raises
from sphinx_testing import with_app

from sphinxcontrib.needs.directives.need import NeedsNoIdException


#  OFFICIAL DOCUMENTATION BUILDS


@with_app(buildername='html', srcdir='../docs')  # , warningiserror=True)
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


@with_app(buildername='needs', srcdir='../docs')
def test_build_json(app, status, warning):
    app.builder.build_all()


# Test with needs_id_required=True and missing ids in docs.
@raises(NeedsNoIdException)
@with_app(buildername='html', srcdir='../docs', confoverrides={"needs_id_required": True})
def test_id_required_build_html(app, status, warning):
    app.builder.build_all()
