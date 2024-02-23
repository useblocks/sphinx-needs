import json
from pathlib import Path

import pytest


def is_need_present(need_id, html, needs_list, is_present=True):
    assert (
        is_need_in_html(need_id, html) is is_present
    ), f"{need_id} should {'not ' if not is_present else ''}be present in html"

    assert (
        is_need_in_needtable(need_id, html) is is_present
    ), f"{need_id} should {'not ' if not is_present else ''}be present in needtable"

    assert (
        is_need_in_needlist(need_id, html) is is_present
    ), f"{need_id} should {'not ' if not is_present else ''}be present in needlist"

    assert (
        need_id in needs_list
    ) is is_present, f"{need_id} should {'not ' if not is_present else ''}be present in needs.json"


def is_need_in_html(need_id, html):
    return 'id="' + need_id + '">' in html


def is_need_in_needtable(need_id, html):
    return (
        '<td class="needs_id"><p><a class="reference internal" href="#' + need_id + '">' + need_id + "</a></p></td>"
        in html
    )


def is_need_in_needlist(need_id, html):
    return '<div class="line"><a class="reference external" href="#' + need_id + '">' + need_id + ":" in html


def get_json_needs(needs_file: Path):
    with open(needs_file) as file:
        data = json.load(file)
        return data["versions"][data["current_version"]]["needs"]


@pytest.mark.parametrize(
    "test_app",
    [
        {"buildername": "html", "srcdir": "doc_test/doc_directive_only", "tags": ["tag_a"]},
    ],
    indirect=True,
)
def test_need_excluded_under_only_a(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    needs_list = get_json_needs(Path(app.outdir, "needs.json"))

    is_need_present("REQ_000", html, needs_list)
    is_need_present("REQ_001", html, needs_list)
    is_need_present("REQ_001_1", html, needs_list)
    is_need_present("REQ_002", html, needs_list, False)
    is_need_present("REQ_003", html, needs_list)
    is_need_present("REQ_004", html, needs_list)


@pytest.mark.parametrize(
    "test_app",
    [
        {"buildername": "html", "srcdir": "doc_test/doc_directive_only", "tags": ["tag_b"]},
    ],
    indirect=True,
)
def test_need_excluded_under_only_b(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    needs_list = get_json_needs(Path(app.outdir, "needs.json"))

    is_need_present("REQ_000", html, needs_list)
    is_need_present("REQ_001", html, needs_list, False)
    is_need_present("REQ_001_1", html, needs_list, False)
    is_need_present("REQ_002", html, needs_list)
    is_need_present("REQ_003", html, needs_list)
    is_need_present("REQ_004", html, needs_list)


@pytest.mark.parametrize("test_app", [{"buildername": "html", "srcdir": "doc_test/doc_directive_only"}], indirect=True)
def test_need_excluded_under_only_no_tag(test_app):
    app = test_app
    app.build()
    html = Path(app.outdir, "index.html").read_text()
    needs_list = get_json_needs(Path(app.outdir, "needs.json"))

    is_need_present("REQ_000", html, needs_list)
    is_need_present("REQ_001", html, needs_list, False)
    is_need_present("REQ_001_1", html, needs_list, False)
    is_need_present("REQ_002", html, needs_list, False)
    is_need_present("REQ_003", html, needs_list, False)
    is_need_present("REQ_004", html, needs_list)
