"""The ids ``test-file``, ``test-suite`` and ``test-case`` give a need without ``:id:``,
pinned byte for byte over a table of shapes.

Each such id is the need type's NAME (``testfile``, not the type's prefix ``TF_``)
followed by a hash of the directive's title, shaped by ``needs_id_length`` and
``needs_id_from_title``. Every row of :data:`DIRECTIVES` is one directive of the page
every column of :data:`CONFIGS` builds; :data:`EXPECTED` is what each gave when the id
was derived through Sphinx-Needs' private ``_make_hashed_id`` (#2407).
"""

from typing import Any

import pytest

from sphinx_needs.data import SphinxNeedsData

LONG = (
    "A long title, well past the needs_max_title_length a project sets, "
    "so the need directive would trim it"
)
UNICODE = "Prüfung der Größe — 測試 ß"
REPORT = (
    b'<testsuite name="S" tests="1">'
    b'<testcase classname="C" name="c" time="0.1"/>'
    b"</testsuite>"
)

#: one directive per row: (directive, title, its options beyond the report's, content)
DIRECTIVES: list[tuple[str, str, str, str]] = [
    ("test-file", "Short", "", ""),
    ("test-file", "Titled", "", "The body text."),
    ("test-file", LONG, "", ""),
    ("test-file", UNICODE, "", ""),
    ("test-file", "Given", "   :id: TF_GIVEN\n", ""),
    ("test-suite", "Short", "   :suite: S\n", ""),
    ("test-suite", UNICODE, "   :suite: S\n", "The body text."),
    ("test-case", "Short", "   :suite: S\n   :case: c\n", ""),
    ("test-case", UNICODE, "   :suite: S\n   :case: c\n", ""),
]

#: a project setting that shapes a generated id: its configuration overrides
CONFIGS: dict[str, dict[str, Any]] = {
    "default": {},
    "id_length_10": {"needs_id_length": 10},
    "id_from_title": {"needs_id_from_title": True, "needs_id_length": 40},
    "max_title_length": {"needs_max_title_length": 10},
    "own_type_names": {
        "tr_file": ["test-file", "ownfile", "Own-File", "OF_", "#ffffff", "node"],
        "tr_suite": ["test-suite", "ownsuite", "Own-Suite", "OS_", "#cccccc", "folder"],
        "tr_case": ["test-case", "owncase", "Own-Case", "OC_", "#999999", "rectangle"],
    },
}

#: every directive's id per configuration at ``c1562e058``, through ``_make_hashed_id``
EXPECTED: dict[str, list[str]] = {
    "default": [
        "testfile0FE7D",
        "testfile9B65B",
        "testfile82586",
        "testfile7D3A6",
        "TF_GIVEN",
        "testsuite0FE7D",
        "testsuite7D3A6",
        "testcase0FE7D",
        "testcase7D3A6",
    ],
    "id_length_10": [
        "testfile0FE7D82F25",
        "testfile9B65BAB658",
        "testfile82586F5653",
        "testfile7D3A62473F",
        "TF_GIVEN",
        "testsuite0FE7D82F25",
        "testsuite7D3A62473F",
        "testcase0FE7D82F25",
        "testcase7D3A62473F",
    ],
    "id_from_title": [
        "testfileSHORT_0FE7D82F25A3015040A206E54F9C1D3A97",
        "testfileTITLED_9B65BAB65820ABB6A6658EEC8FFDBF5AB",
        "testfileA_LONG_TITLE,_WELL_PAST_THE_NEEDS_MAX_TI",
        "testfilePRÜFUNG_DER_GRÖSSE_—_測試_SS_7D3A62473FC0B",
        "TF_GIVEN",
        "testsuiteSHORT_0FE7D82F25A3015040A206E54F9C1D3A97",
        "testsuitePRÜFUNG_DER_GRÖSSE_—_測試_SS_7D3A62473FC0B",
        "testcaseSHORT_0FE7D82F25A3015040A206E54F9C1D3A97",
        "testcasePRÜFUNG_DER_GRÖSSE_—_測試_SS_7D3A62473FC0B",
    ],
    "max_title_length": [
        "testfile0FE7D",
        "testfile9B65B",
        "testfile82586",
        "testfile7D3A6",
        "TF_GIVEN",
        "testsuite0FE7D",
        "testsuite7D3A6",
        "testcase0FE7D",
        "testcase7D3A6",
    ],
    "own_type_names": [
        "ownfile0FE7D",
        "ownfile9B65B",
        "ownfile82586",
        "ownfile7D3A6",
        "TF_GIVEN",
        "ownsuite0FE7D",
        "ownsuite7D3A6",
        "owncase0FE7D",
        "owncase7D3A6",
    ],
}


def _page() -> str:
    page = ""
    for directive, title, options, content in DIRECTIVES:
        page += f".. {directive}:: {title}\n   :file: report.xml\n{options}"
        page += f"\n   {content}\n\n" if content else "\n"
    return page


@pytest.mark.parametrize("config", list(CONFIGS))
def test_the_ids_are_unchanged_for_every_shape(build_page, config: str) -> None:
    app, warnings = build_page(
        _page(),
        files={"report.xml": REPORT},
        confoverrides=CONFIGS[config],
        conf='needs_id_regex = ".*"\n',
    )
    assert warnings == ""
    needs = SphinxNeedsData(app.env).get_needs_view()
    by_line = sorted(needs.values(), key=lambda need: need["lineno"] or 0)
    assert [need["id"] for need in by_line] == EXPECTED[config]
