import json
import responses
from pathlib import Path
from random import randrange
import re
import uuid

import six
from nose.tools import raises
from sphinx_testing import with_app

from sphinxcontrib.needs.api.need import NeedsNoIdException
from tests.data.service_github import GITHUB_SPECIFIC_COMMIT_ANSWER, GITHUB_ISSUE_SEARCH_ANSWER, GITHUB_SPECIFIC_ISSUE_ANSWER, \
     GITHUB_SEARCH_COMMIT_ANSWER


def random_data_callback(request):
    """
    Response data callback, which injects random ids, so that the generated needs get always a unique id and no
    exceptions get thrown.
    """
    if re.match(r'/search/issues', request.path_url):
        data = GITHUB_ISSUE_SEARCH_ANSWER
        data['items'][0]['number'] = randrange(10000)
    elif re.match(r'/.+/issue/.+', request.path_url):
        data = GITHUB_SPECIFIC_ISSUE_ANSWER
        data['number'] = randrange(10000)
    elif re.match(r'/.+/pulls/.+', request.path_url):
        # data = GITHUB_SEARCH_COMMIT_ANSWER
        data = GITHUB_SPECIFIC_ISSUE_ANSWER
        data['number'] = randrange(10000)
    elif re.match(r'/search/commits', request.path_url):
        data = GITHUB_SEARCH_COMMIT_ANSWER
        data['number'] = randrange(10000)
    elif re.match(r'/.*/commits/*', request.path_url):
        data = GITHUB_SPECIFIC_COMMIT_ANSWER
        data['sha'] = uuid.uuid4().hex
    else:
        print(request.path_url)
    return 200, [], json.dumps(data)



#  OFFICIAL DOCUMENTATION BUILDS

@responses.activate
@with_app(buildername='html', srcdir='../docs')  # , warningiserror=True)
def test_build_html(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
    app.builder.build_all()


@responses.activate
@with_app(buildername='singlehtml', srcdir='../docs')
def test_build_singlehtml(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
    app.builder.build_all()


@responses.activate
@with_app(buildername='latex', srcdir='../docs')
def test_build_latex(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
    app.builder.build_all()


@responses.activate
@with_app(buildername='epub', srcdir='../docs')
def test_build_epub(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
    app.builder.build_all()


@responses.activate
@with_app(buildername='json', srcdir='../docs')
def test_build_json(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
    app.builder.build_all()


@responses.activate
@with_app(buildername='needs', srcdir='../docs')
def test_build_needs(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
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
@responses.activate
@with_app(buildername='html', srcdir='../docs', confoverrides={"needs_id_required": True})
def test_id_required_build_html(app, status, warning):
    responses.add_callback(responses.GET, re.compile(r'https://api.github.com/.*'), callback=random_data_callback,
                           content_type='application/json')
    app.builder.build_all()
