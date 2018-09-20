import json
import os

import six
from nose.tools import raises
from sphinx_testing import with_app

from sphinxcontrib.needs.directives.need import NeedsNoIdException
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

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
def test_build_needs(app, status, warning):
    app.builder.build_all()
    json_text = Path(app.outdir, 'needs.json').read_text()
    needs_data = json.loads(json_text)

    # Validate top-level data
    assert 'created' in needs_data
    assert 'project' in needs_data
    assert 'versions' in needs_data
    assert 'current_version' in needs_data
    current_version = needs_data['current_version']
    assert current_version == app.config.version

    # Validate current version data
    current_version_data = needs_data['versions'][current_version]
    assert 'created' in current_version_data
    assert 'needs' in current_version_data
    assert 'needs_amount' in current_version_data
    assert 'needs_amount' in current_version_data
    assert (current_version_data['needs_amount']
            == len(current_version_data['needs']))

    # Validate individual needs data
    current_needs = current_version_data['needs']
    expected_keys = ('description', 'id', 'links', 'sections', 'status',
                     'tags', 'title', 'type_name')
    for need in six.itervalues(current_needs):
        assert all(key in need for key in expected_keys)


# Test with needs_id_required=True and missing ids in docs.
@raises(NeedsNoIdException)
@with_app(buildername='html', srcdir='../docs', confoverrides={"needs_id_required": True})
def test_id_required_build_html(app, status, warning):
    app.builder.build_all()
