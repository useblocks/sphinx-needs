import json
import os.path
import re
import sys
import tempfile
import uuid
from pathlib import Path
from random import randrange

import pytest
import responses
import sphinx.application

from sphinx_needs.api.need import NeedsNoIdException
from tests.data.service_github import (
    GITHUB_ISSUE_SEARCH_ANSWER,
    GITHUB_SEARCH_COMMIT_ANSWER,
    GITHUB_SPECIFIC_COMMIT_ANSWER,
    GITHUB_SPECIFIC_ISSUE_ANSWER,
)


def random_data_callback(request):
    """
    Response data callback, which injects random ids, so that the generated needs get always a unique id and no
    exceptions get thrown.
    """
    if re.match(r"/search/issues", request.path_url):
        data = GITHUB_ISSUE_SEARCH_ANSWER
        data["items"][0]["number"] = randrange(10000)
    elif re.match(r"/.+/issue/.+", request.path_url) or re.match(r"/.+/pulls/.+", request.path_url):
        data = GITHUB_SPECIFIC_ISSUE_ANSWER
        data["number"] = randrange(10000)
    elif re.match(r"/search/commits", request.path_url):
        data = GITHUB_SEARCH_COMMIT_ANSWER
        data["number"] = randrange(10000)
    elif re.match(r"/.*/commits/*", request.path_url):
        data = GITHUB_SPECIFIC_COMMIT_ANSWER
        data["sha"] = uuid.uuid4().hex
    else:
        print(request.path_url)
    return 200, [], json.dumps(data)


#  OFFICIAL DOCUMENTATION BUILDS


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "../docs"}], indirect=True)
def test_build_html(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
    assert build_dir / "datatables_loader.js" in files
    assert build_dir / "DataTables-1.10.16" / "js" / "jquery.dataTables.min.js" in files


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/generic_doc"}], indirect=True)
def test_build_html_parallel(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()

    # Check if static files got copied correctly.
    build_dir = Path(app.outdir) / "_static" / "sphinx-needs" / "libs" / "html"
    files = [f for f in build_dir.glob("**/*") if f.is_file()]
    assert build_dir / "sphinx_needs_collapse.js" in files
    assert build_dir / "datatables_loader.js" in files
    assert build_dir / "DataTables-1.10.16" / "js" / "jquery.dataTables.min.js" in files


@pytest.mark.skipif(sys.platform == "win32", reason="assert fails on windows, need to fix later.")
@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/generic_doc"}], indirect=True)
def test_html_head_files(test_app):
    app = test_app
    app.builder.build_all()

    from lxml import html as html_parser

    # check usage in project root level
    html_path = str(Path(app.outdir, "index.html"))
    root_tree = html_parser.parse(html_path)
    script_nodes = root_tree.xpath("/html/head/script")
    script_files = [x.attrib["src"] for x in script_nodes]
    assert script_files.count("_static/sphinx-needs/libs/html/datatables.min.js") == 1

    link_nodes = root_tree.xpath("/html/head/link")
    link_files = [x.attrib["href"] for x in link_nodes]
    assert link_files.count("_static/sphinx-needs/modern.css") == 1

    # Checks if not \ (Backslash) is found as path of js/css files
    # This can happen when working on Windows (would be a bug ;) )
    for head_file in script_files + link_files:
        assert "\\" not in head_file


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "singlehtml", "srcdir": "../docs"}], indirect=True)
def test_build_singlehtml(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "latex", "srcdir": "doc_test/doc_basic"}], indirect=True)
def test_build_latex(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "epub", "srcdir": "doc_test/doc_basic"}], indirect=True)
def test_build_epub(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "json", "srcdir": "doc_test/doc_basic"}], indirect=True)
def test_build_json(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()


@responses.activate
@pytest.mark.parametrize("test_app", [{"buildername": "needs", "srcdir": "../docs"}], indirect=True)
def test_build_needs(test_app):
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    app = test_app
    app.builder.build_all()
    json_text = Path(app.outdir, "needs.json").read_text()
    needs_data = json.loads(json_text)

    # Validate top-level data
    assert "created" in needs_data
    assert "project" in needs_data
    assert "versions" in needs_data
    assert "current_version" in needs_data
    current_version = needs_data["current_version"]
    assert current_version == app.config.version

    # Validate current version data
    current_version_data = needs_data["versions"][current_version]
    assert "created" in current_version_data
    assert "needs" in current_version_data
    assert "needs_amount" in current_version_data
    assert "needs_amount" in current_version_data
    assert current_version_data["needs_amount"] == len(current_version_data["needs"])

    # Validate individual needs data
    current_needs = current_version_data["needs"]
    expected_keys = ("description", "id", "links", "sections", "status", "tags", "title", "type_name")
    for need in current_needs.values():
        assert all(key in need for key in expected_keys)


# Test with needs_id_required=True and missing ids in docs.
@responses.activate
@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "../docs", "confoverrides": {"needs_id_required": True}}],
    indirect=True,
)
def test_id_required_build_html(test_app):
    with pytest.raises(NeedsNoIdException):
        responses.add_callback(
            responses.GET,
            re.compile(r"https://api.github.com/.*"),
            callback=random_data_callback,
            content_type="application/json",
        )
        responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

        app = test_app
        app.builder.build_all()


@responses.activate
def test_sphinx_api_build():
    """
    Tests a build via the Sphinx Build API.
    It looks like that there are scenarios where this specific build makes trouble but no others.
    """
    responses.add_callback(
        responses.GET,
        re.compile(r"https://api.github.com/.*"),
        callback=random_data_callback,
        content_type="application/json",
    )
    responses.add(responses.GET, re.compile(r"https://avatars.githubusercontent.com/.*"), body="")

    temp_dir = tempfile.mkdtemp()
    src_dir = os.path.join(os.path.dirname(__file__), "doc_test", "doc_basic")

    sphinx_app = sphinx.application.Sphinx(
        srcdir=src_dir,
        confdir=src_dir,
        outdir=temp_dir,
        doctreedir=temp_dir,
        buildername="html",
        parallel=4,
        freshenv=True,
    )
    sphinx_app.build()
    assert sphinx_app.statuscode == 0
