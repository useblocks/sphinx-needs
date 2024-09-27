import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from sphinx.util.console import strip_colors

from sphinx_needs.filter_common import filter_needs_parts, filter_needs_view
from sphinx_needs.views import NeedsView


@pytest.mark.parametrize(
    "test_app",
    [{"buildername": "html", "srcdir": "doc_test/filter_doc"}],
    indirect=True,
)
def test_filter_build_html(test_app):
    app = test_app
    app.build()
    warnings = strip_colors(app._warning.getvalue()).replace(
        str(app.srcdir) + os.path.sep, "<srcdir>/"
    )
    # print(warnings.splitlines())

    expected_warnings = [
        "<srcdir>/index.rst:51: WARNING: Filter 'xxx' not valid. Error: name 'xxx' is not defined. [needs.filter]",
        "<srcdir>/index.rst:54: WARNING: Filter '1' not valid. Error: Filter did not evaluate to a boolean, instead <class 'int'>: 1. [needs.filter]",
        "<srcdir>/index.rst:57: WARNING: Filter 'yyy' not valid. Error: name 'yyy' is not defined. [needs.filter]",
        "<srcdir>/index.rst:60: WARNING: Sorting parameter yyy not valid: Error: 'yyy' [needs]",
        "<srcdir>/index.rst:63: WARNING: Filter 'zzz' not valid. Error: name 'zzz' is not defined. [needs.filter]",
    ]

    assert warnings.splitlines() == expected_warnings

    html = Path(app.outdir, "index.html").read_text()
    assert "story_a_1" in html
    assert "story_b_1" not in html
    assert "story_a_b_1" in html

    assert "req_a_1" not in html
    assert "req_b_1" not in html
    assert "req_c_1" in html

    html_2 = Path(app.outdir, "filter_tags_or.html").read_text()
    assert "req_a" in html_2
    assert "req_b" in html_2
    assert "req_c" in html_2

    html_3 = Path(app.outdir, "filter_all.html").read_text()
    assert "req_a_not" not in html_3
    assert "req_b_found" in html_3
    assert "req_c_not" not in html_3
    assert "req_d_found" in html_3
    assert "story_1_not" not in html_3
    assert "story_2_found" in html_3
    assert "my_test" in html_3

    html_4 = Path(app.outdir, "filter_search.html").read_text()
    assert "search_a" in html_4
    assert "search_b" not in html_4
    assert "search_c" not in html_4
    assert "search_d" not in html_4
    assert "search_2_1" in html_4
    assert "search_2_2" in html_4
    assert "test_email" in html_4

    # nested needs
    html_5 = Path(app.outdir, "nested_needs.html").read_text()
    assert "STORY_PARENT" in html_5
    assert "CHILD_1_STORY" in html_5
    assert "CHILD_2_STORY" in html_5
    assert (
        '<div class="line">child needs: <span class="parent_needs"><span><a class="reference internal" '
        'href="#CHILD_1_STORY" title="STORY_PARENT">CHILD_1_STORY</a></span></span></div>'
        in html_5
    )
    assert (
        '<div class="line">parent needs: <span class="parent_needs"><span><a class="reference internal" '
        'href="#CHILD_1_STORY" title="CHILD_2_STORY">CHILD_1_STORY</a></span></span></div>'
        in html_5
    )

    html_6 = Path(app.outdir, "filter_no_needs.html").read_text()
    assert html_6.count("No needs passed the filters") == 6
    assert html_6.count("Should show no specific message and no default message") == 6
    assert html_6.count("<figure class=") == 3

    assert html_6.count("got filter warning from needtable") == 1
    assert "no filter warning from needtable" not in html_6
    assert html_6.count('<table class="NEEDS_DATATABLES') == 1

    assert html_6.count("got filter warning from needlist") == 1
    assert "no filter warning from needlist" not in html_6

    assert html_6.count("got filter warning from needflow") == 1
    assert "no filter warning from needflow" not in html_6

    assert html_6.count("got filter warning from needgant") == 1
    assert "no filter warning from needgant" not in html_6

    assert (
        html_6.count("got filter warning from needsequence") == 1
    )  # maybe fixed later, now always start node is shown
    assert "no filter warning from needsequence" not in html_6

    assert html_6.count("got filter warning from needpie") == 1
    assert "no filter warning from needpie" not in html_6
    assert '<img alt="_images/need_pie_' in html_6

    assert html_6.count('<p class="needs_filter_warning"') == 18


def create_needs_view():
    needs = [
        {
            "id": "req_a_1",
            "type": "requirement",
            "type_name": "Req",
            "tags": ["a", "b"],
            "status": "",
            "is_external": False,
            "parts": {},
        },
        {
            "id": "req_b_1",
            "type": "requirement",
            "type_name": "Req",
            "tags": ["b", "c"],
            "status": "",
            "is_external": False,
            "parts": {},
        },
        {
            "id": "req_c_1",
            "type": "requirement",
            "type_name": "Req",
            "tags": ["c", "d"],
            "status": "",
            "is_external": False,
            "parts": {},
        },
        {
            "id": "story_a_1",
            "type": "story",
            "type_name": "Story",
            "tags": ["a", "b"],
            "status": "",
            "is_external": False,
            "parts": {},
        },
        {
            "id": "story_b_1",
            "type": "story",
            "type_name": "Story",
            "tags": ["b", "c"],
            "status": "ongoing",
            "is_external": False,
            "parts": {},
        },
        {
            "id": "story_a_b_1",
            "type": "story",
            "type_name": "Story",
            "tags": ["a", "b", "c"],
            "status": "done",
            "is_external": False,
            "parts": {
                "part_a": {
                    "id": "part_a",
                },
            },
        },
    ]

    return NeedsView(_needs={n["id"]: n for n in needs})


std_test_params = (
    ("", list(create_needs_view().keys())),
    ("True", list(create_needs_view().keys())),
    ("xxx", list(create_needs_view().keys())),
    ("not xxx", []),
    ("False", []),
    ("False and False", []),
    ("False and True", []),
    ("True and True", list(create_needs_view().keys())),
    ("True or False", list(create_needs_view().keys())),
    ("id == 'req_a_1'", ["req_a_1"]),
    ("id == 'unknown'", []),
    ("type == 'requirement'", ["req_a_1", "req_b_1", "req_c_1"]),
    ("type == 'unknown'", []),
    ("type == 'requirement' and True", ["req_a_1", "req_b_1", "req_c_1"]),
    ("type == 'requirement' and False", []),
    ("type == 'story' and status == 'done'", ["story_a_b_1"]),
    ("status in ['ongoing', 'done']", ["story_b_1", "story_a_b_1"]),
    ("status in ('ongoing', 'done')", ["story_b_1", "story_a_b_1"]),
    ("status in {'ongoing', 'done'}", ["story_b_1", "story_a_b_1"]),
    ("'d' in tags", ["req_c_1"]),
)


@pytest.mark.parametrize(
    "filter_string, expected_ids", std_test_params, ids=[s for s, _ in std_test_params]
)
def test_filter_needs_view(filter_string, expected_ids):
    mock_config = Mock()
    mock_config.filter_data = {"xxx": True}
    result = filter_needs_view(create_needs_view(), mock_config, filter_string)
    assert {n["id"] for n in result} == set(expected_ids)


part_test_params = (
    ("", list(create_needs_view().keys()) + ["part_a"]),
    ("True", list(create_needs_view().keys()) + ["part_a"]),
    ("xxx", list(create_needs_view().keys()) + ["part_a"]),
    ("not xxx", []),
    ("False", []),
    ("False and False", []),
    ("False and True", []),
    ("True and True", list(create_needs_view().keys()) + ["part_a"]),
    ("True or False", list(create_needs_view().keys()) + ["part_a"]),
    ("id == 'req_a_1'", ["req_a_1"]),
    ("id == 'unknown'", []),
    ("type == 'requirement'", ["req_a_1", "req_b_1", "req_c_1"]),
    ("type == 'unknown'", []),
    ("type == 'requirement' and True", ["req_a_1", "req_b_1", "req_c_1"]),
    ("type == 'requirement' and False", []),
    ("type == 'story' and status == 'done'", ["story_a_b_1", "part_a"]),
    ("status in ['ongoing', 'done']", ["story_b_1", "story_a_b_1", "part_a"]),
    ("status in ('ongoing', 'done')", ["story_b_1", "story_a_b_1", "part_a"]),
    ("status in {'ongoing', 'done'}", ["story_b_1", "story_a_b_1", "part_a"]),
    ("'d' in tags", ["req_c_1"]),
    ("id == 'part_a'", ["part_a"]),
    ("id in ['part_a', 'req_a_1']", ["part_a", "req_a_1"]),
    ("id in ['part_a', 'story_a_b_1']", ["story_a_b_1", "part_a"]),
)


@pytest.mark.parametrize(
    "filter_string, expected_ids",
    part_test_params,
    ids=[s for s, _ in part_test_params],
)
def test_filter_needs_parts(filter_string, expected_ids):
    mock_config = Mock()
    mock_config.filter_data = {"xxx": True}
    result = filter_needs_parts(
        create_needs_view().to_list_with_parts(), mock_config, filter_string
    )
    assert {n["id"] for n in result} == set(expected_ids)
