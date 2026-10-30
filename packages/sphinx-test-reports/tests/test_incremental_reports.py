"""An incremental build re-reads the pages a report is read on (#2424), and its test
needs equal a fresh build's: their pages, their needs.json and their hops.

Every directive that reads a report makes its page depend on it, on the path it opens,
whether it could read it or not: an edited, a created or a fixed report re-reads the
page. A test need compares as Sphinx-Needs compares any need in an incremental build,
by its source without its lines (``NeedItemSource._without_lines``, #2414).

The oracle is a fresh build of the same sources.
"""

from __future__ import annotations

import json
import pickle
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

from sphinx_needs.data import SphinxNeedsData

#: The report each page reads, by name; every case carries a file and a line.
REPORT = (
    '<testsuites><testsuite name="pytest" tests="3">'
    '<testcase classname="tests.test_a" name="test_one" file="tests/test_a.py" line="3"/>'
    '<testcase classname="tests.test_a.TestK" name="test_two" file="tests/test_a.py" '
    'line="9"/>'
    '<testcase classname="tests.test_a" name="test_three[1]" file="tests/test_a.py" '
    'line="14"/>'
    "</testsuite></testsuites>"
)

JSON_REPORT = json.dumps(
    [
        {
            "name": "s1",
            "tests": 1,
            "errors": 0,
            "failures": 0,
            "skips": 0,
            "passed": 1,
            "time": 1,
            "testcase": [
                {"name": "t1", "classname": "c1", "file": "tests/j.py", "line": 2}
            ],
        }
    ]
)

ENV_REPORT = json.dumps(
    {"py": {"host": "h", "installed_packages": ["a==1"], "platform": "linux"}}
)

CONF = """\
extensions = ["sphinx_needs", "sphinx_test_reports"]
needs_id_regex = ".*"
needs_build_json = True
exclude_patterns = ["_build"]
tr_json_mapping = {
    "cfg": {
        "testsuite": {
            "name": (["name"], "unknown"), "tests": (["tests"], 0),
            "errors": (["errors"], 0), "failures": (["failures"], 0),
            "skips": (["skips"], 0), "passed": (["passed"], 0),
            "time": (["time"], 0), "testcases": (["testcase"], []),
        },
        "testcase": {
            "name": (["name"], "unknown"), "classname": (["classname"], "unknown"),
            "file": (["file"], "unknown"), "line": (["line"], -1),
            "time": (["time"], 0), "result": (["result"], "passed"),
            "type": (["type"], ""), "text": (["text"], ""),
            "message": (["message"], ""), "system-out": (["system-out"], ""),
        },
    }
}
"""

#: One page per way a report is read; each reads its own report.
FILES = {
    "conf.py": CONF,
    "index.rst": """\
Index
=====

.. toctree::

   file
   suite
   case
   report
   outside
   json
   results
   env
   other
""",
    "file.rst": """\
File
====

.. test-file:: A file
   :file: reports/file.xml
   :id: TF_F
   :auto_suites:
   :auto_cases:
""",
    "suite.rst": """\
Suite
=====

.. test-suite:: A suite
   :file: reports/suite.xml
   :id: TS_S
   :suite: pytest
""",
    "case.rst": """\
Case
====

.. test-case:: A case
   :file: reports/case.xml
   :id: TC_C
   :suite: pytest
   :case: test_two
   :classname: tests.test_a.TestK
""",
    "report.rst": """\
Report
======

Some text.

.. test-report:: A report
   :file: reports/report.xml
   :id: TR_R
""",
    "outside.rst": """\
Outside
=======

.. test-file:: Outside the source directory
   :file: ../outside/outside.xml
   :id: TF_O
   :auto_suites:
   :auto_cases:
""",
    "json.rst": """\
JSON
====

.. test-file:: A JSON report
   :file: reports/r.json
   :id: TF_J
   :auto_suites:
   :auto_cases:
""",
    "results.rst": """\
Results
=======

.. test-results:: reports/results.xml
""",
    "env.rst": """\
Env
===

.. test-env:: reports/env.json
""",
    "other.rst": """\
Other
=====

Reads no report.
""",
    "reports/file.xml": REPORT,
    "reports/suite.xml": REPORT,
    "reports/case.xml": REPORT,
    "reports/report.xml": REPORT,
    "../outside/outside.xml": REPORT,
    "reports/r.json": JSON_REPORT,
    "reports/results.xml": REPORT,
    "reports/env.json": ENV_REPORT,
}

#: A case renamed in a report.
_RENAMED = ('name="test_two"', 'name="test_two_renamed"')


def _edit(name: str, old: str, new: str) -> dict[str, str | None]:
    text = FILES[name]
    assert text.count(old) == 1, (name, old)
    return {name: text.replace(old, new)}


#: ``(before, after)``: what changes between the two builds (``None``: absent).
SCENARIOS: dict[str, tuple[dict[str, str | None], dict[str, str | None]]] = {
    # the report changes: the page re-reads it
    "report-of-a-test-file": ({}, _edit("reports/file.xml", *_RENAMED)),
    "report-of-a-test-suite": (
        {},
        _edit("reports/suite.xml", 'tests="3"', 'tests="4"'),
    ),
    "report-of-a-test-case": (
        {},
        _edit("reports/case.xml", 'line="9"', 'line="10"'),
    ),
    "report-of-a-test-report": ({}, _edit("reports/report.xml", *_RENAMED)),
    "report-outside-the-source-directory": (
        {},
        _edit("../outside/outside.xml", *_RENAMED),
    ),
    "json-report": ({}, _edit("reports/r.json", '"t1"', '"t1_renamed"')),
    "report-of-test-results": ({}, _edit("reports/results.xml", *_RENAMED)),
    "report-of-test-env": ({}, _edit("reports/env.json", '"a==1"', '"a==2"')),
    # a report that could not be read: missing, then created; unreadable, then fixed
    "missing-report-created": ({"reports/file.xml": None}, {}),
    "unreadable-report-fixed": ({"reports/case.xml": "<testsuites"}, {}),
    # the page changes: lines inserted above the test-file, the test-report's page edited
    "lines-above-a-test-file": (
        {},
        _edit("file.rst", "====\n\n", "====\n\nTwo\nlines.\n\n"),
    ),
    "test-report-page-edited": (
        {},
        _edit("report.rst", "Some text.\n", "Some text.\n\nMore text, above it.\n"),
    ),
}

#: The scenarios that are a report changing: before #2424 nothing was re-read.
REPORT_SCENARIOS = [
    name
    for name in SCENARIOS
    if name not in ("lines-above-a-test-file", "test-report-page-edited")
]


def _write(root: Path, files: dict[str, str | None]) -> Path:
    """Write the project under ``root/src``; a file whose text is the same is left
    untouched (Sphinx compares modification times), and ``None`` removes one."""
    srcdir = root / "src"
    for name, text in files.items():
        path = srcdir / name
        if text is None:
            path.unlink(missing_ok=True)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    return srcdir


def _build(
    make_app: Callable[..., SphinxTestApp], srcdir: Path, *, fresh: bool
) -> tuple[SphinxTestApp, list[str]]:
    """Build; return the app and the documents its incremental read re-read."""
    app = make_app("html", srcdir=srcdir, freshenv=fresh)
    app.build()
    status = strip_colors(app._status.getvalue())
    return app, re.findall(r"reading sources\.\.\. \[\s*\d+%\] (\S+)", status)


_BODY = re.compile(
    r'<div class="body" role="main">(.*?)<div class="sphinxsidebar"', re.DOTALL
)
_CONTAINER_ID = re.compile(r"SNCB-[0-9a-f]+")


def _pages(outdir: Path) -> dict[str, str]:
    """The body of every page, the part a need can show up in."""
    pages = {}
    for path in sorted(outdir.glob("*.html")):
        if path.stem in {"genindex", "search", "permalink"}:
            continue
        match = _BODY.search(path.read_text(encoding="utf-8"))
        assert match is not None, path
        pages[path.stem] = _CONTAINER_ID.sub("SNCB-", match.group(1))
    return pages


def _needs_json(outdir: Path) -> dict[str, object]:
    data = json.loads((outdir / "needs.json").read_text(encoding="utf-8"))
    return next(iter(data["versions"].values()))["needs"]


def _sources(app: SphinxTestApp) -> dict[str, object]:
    """Every need's lineno and hops (paths are relative, so two projects compare)."""
    return {
        need_id: (need["lineno"], need.source.hops)
        for need_id, need in SphinxNeedsData(app.env).get_needs_view().items()
    }


def _assert_equivalent(
    make_app: Callable[..., SphinxTestApp], tmp_path: Path, scenario: str
) -> list[str]:
    """Build, edit, build incrementally, and compare with a fresh build of the edit.

    :return: The documents the incremental build re-read.
    """
    before, after = SCENARIOS[scenario]
    first = {**FILES, **before}
    incremental = _write(tmp_path / "incremental", first)
    _build(make_app, incremental, fresh=True)
    _write(tmp_path / "incremental", {**FILES, **after})
    app, read = _build(make_app, incremental, fresh=False)

    fresh = _write(tmp_path / "fresh", {**FILES, **after})
    fresh_app, _ = _build(make_app, fresh, fresh=True)

    outdir, fresh_outdir = Path(app.outdir), Path(fresh_app.outdir)
    got, expected = _pages(outdir), _pages(fresh_outdir)
    stale = sorted(name for name in expected if got.get(name) != expected[name])
    assert stale == [], f"pages not re-written: {stale} (read {read})"
    got_needs, expected_needs = _needs_json(outdir), _needs_json(fresh_outdir)
    assert (
        sorted(
            need_id
            for need_id in got_needs.keys() | expected_needs.keys()
            if got_needs.get(need_id) != expected_needs.get(need_id)
        )
        == []
    )
    assert _sources(app) == _sources(fresh_app)
    return read


def test_the_project_builds_cleanly(make_app, tmp_path):
    """The fixture is what the scenarios assume: no warning, every page a need."""
    srcdir = _write(tmp_path, FILES)
    app, _ = _build(make_app, srcdir, fresh=True)
    assert strip_colors(app._warning.getvalue()) == ""
    needs = SphinxNeedsData(app.env).get_needs_view()
    assert {need["docname"] for need in needs.values()} == {
        "file",
        "suite",
        "case",
        "report",
        "outside",
        "json",
    }


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_an_incremental_build_equals_a_fresh_build(make_app, tmp_path, scenario):
    _assert_equivalent(make_app, tmp_path, scenario)


@pytest.mark.parametrize(
    ("scenario", "page"),
    [
        ("report-of-a-test-file", "file"),
        ("report-of-a-test-report", "report"),
        ("report-outside-the-source-directory", "outside"),
        ("json-report", "json"),
        ("report-of-test-results", "results"),
        ("report-of-test-env", "env"),
        ("missing-report-created", "file"),
        ("unreadable-report-fixed", "case"),
    ],
)
def test_a_report_change_re_reads_only_the_pages_reading_it(
    make_app, tmp_path, scenario, page
):
    """Only the page reading the report is read again, not every page."""
    assert _assert_equivalent(make_app, tmp_path, scenario) == [page]


def test_an_environment_pickled_by_an_earlier_release_is_read_again(make_app, tmp_path):
    """An environment an earlier release pickled holds its test needs as it recorded
    them -- the line in the expanded input, no hops -- and nothing in the sources
    changed: the extension's ``env_version`` is what has the upgraded build read every
    page again. An earlier release declared none, which is what is simulated here."""
    srcdir = _write(tmp_path, FILES)
    app, _ = _build(make_app, srcdir, fresh=True)
    pickled = Path(app.doctreedir, "environment.pickle")
    env = pickle.loads(pickled.read_bytes())
    env.version = {
        name: version
        for name, version in env.version.items()
        if name != "sphinx_test_reports"
    }
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    app, read = _build(make_app, srcdir, fresh=False)
    assert "file" in read
    assert "report" in read
