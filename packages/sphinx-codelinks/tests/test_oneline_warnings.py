# @Test suite for the one-line parser's warnings in a build, TEST_ONELINE_WARNINGS_1, test, [IMPL_OLP_1]
"""A malformed one-line marker is reported in the build, at its source line (#2076).

Every case builds a copy of ``doc_test/need_id_refs`` (see ``test_need_id_refs``), whose
``index`` traces the whole of project ``src``, with ``src/refs.cpp`` reduced to one
reference that resolves, so that the only warnings a build can emit are the one-line
parser's.
"""

import re
from pathlib import Path

import pytest
from sphinx.util.console import strip_colors
from sphinx.util.parallel import parallel_available

from sphinx_needs_testkit import assert_no_warnings, build_warnings

from .test_config_only_refs import NO_DIRECTIVE
from .test_need_id_refs import _SHOWS_WARNING_TYPES, _build, _json, _MakeApp, _project

#: ``refs.cpp`` with nothing to warn about
REFS = {"src/refs.cpp": "// @need-ids: REQ_001\nvoid implements_a() {}\n"}

#: a ``[[ ... ]]`` style with two required fields, ``id`` and ``title``
BRACKETS = (
    "\n[codelinks.projects.src.analyse.oneline_comment_style]\n"
    'start_sequence = "[["\n'
    'end_sequence = "]]"\n'
    "needs_fields = [\n"
    '  { name = "id" },\n'
    '  { name = "title" },\n'
    '  { name = "type", default = "impl" },\n'
    '  { name = "links", type = "list[str]", default = [] },\n'
    "]\n"
)
#: line 3 is malformed: one field where two are required
BRACKETED = (
    "// [[ IMPL_1, first ]]\n"
    "void first() {}\n"
    "// [[ only-title ]]\n"
    "void second() {}\n"
    "// [[ IMPL_3, third ]]\n"
    "void third() {}\n"
)
#: the default ``@`` style on a Doxygen-documented file
DOXYGEN = (
    "/**\n"
    " * @brief Does a, IMPL_BRIEF\n"
    " * @param x the value\n"
    " * @return nothing\n"
    " * @see A, B, C, D, E\n"
    " */\n"
    "void documented(int x) {}\n"
)


def _oneline(location: str, message: str) -> str:
    suffix = " [codelinks.oneline]" if _SHOWS_WARNING_TYPES else ""
    return f"{location}: WARNING: {message}{suffix}"


TOO_FEW = _oneline(
    "src/x.cpp:3", "too_few_fields: 1 given fields. They shall be more than 2"
)


def test_a_malformed_marker_warns_at_its_source_line(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """One warning, at the file and line, typed ``codelinks.oneline``; the build goes
    on and the valid markers' needs exist."""
    _project(tmp_path, toml_extra=BRACKETS, files={**REFS, "src/x.cpp": BRACKETED})
    app = _build(tmp_path, make_app)

    assert app.statuscode == 0
    assert build_warnings(app) == [TOO_FEW]
    needs = _json(app)["needs"]
    assert {"IMPL_1", "IMPL_3"} <= set(needs)


def test_the_warning_is_suppressible(tmp_path: Path, make_app: _MakeApp) -> None:
    """One ``suppress_warnings`` entry silences every kind."""
    _project(tmp_path, toml_extra=BRACKETS, files={**REFS, "src/x.cpp": BRACKETED})
    app = _build(
        tmp_path,
        make_app,
        confoverrides={"suppress_warnings": ["codelinks.oneline"]},
    )

    assert_no_warnings(app)
    assert {"IMPL_1", "IMPL_3"} <= set(_json(app)["needs"])


def test_documentation_tags_on_the_default_style_do_not_warn(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """``@param`` and ``@return`` are not markers; ``@brief Does a, IMPL_BRIEF`` is a
    need, as it always was; ``@see A, B, C, D, E`` has five fields where four are
    allowed, and warns at its line."""
    _project(tmp_path, files={**REFS, "src/x.cpp": DOXYGEN})
    app = _build(tmp_path, make_app)

    assert build_warnings(app) == [
        _oneline(
            "src/x.cpp:5", "too_many_fields: 5 given fields. They shall be less than 4"
        )
    ]
    assert _json(app)["needs"]["IMPL_BRIEF"]["title"] == "brief Does a"


def test_a_config_only_project_reports_none(tmp_path: Path, make_app: _MakeApp) -> None:
    """A project no directive traces creates no needs, so its malformed markers are
    not reported; the summary line still counts its one-line needs."""
    _project(
        tmp_path,
        toml_extra=BRACKETS,
        files={**REFS, **NO_DIRECTIVE, "src/x.cpp": BRACKETED},
    )
    app = _build(tmp_path, make_app)

    assert_no_warnings(app)
    status = strip_colors(app._status.getvalue())
    assert "2 one-line needs not created (no src-trace directive)" in status


@pytest.mark.skipif(
    not parallel_available, reason="Sphinx reads sources in parallel on POSIX only"
)
def test_a_worker_s_warning_reaches_the_log(tmp_path: Path, make_app: _MakeApp) -> None:
    """``-j 2`` reads the directive in a worker; Sphinx forwards its log records."""
    _project(tmp_path, toml_extra=BRACKETS, files={**REFS, "src/x.cpp": BRACKETED})
    app = _build(tmp_path, make_app, parallel=2)

    status = strip_colors(app._status.getvalue())
    assert re.search(r"reading sources\.\.\. \[\s*\d+%\] \S+ \.\. \S+", status)
    assert build_warnings(app) == [TOO_FEW]
