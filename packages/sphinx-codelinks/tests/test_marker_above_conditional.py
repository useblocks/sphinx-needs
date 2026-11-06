# @Test suite for the warning on a marker above a preprocessor conditional, TEST_ABOVE_COND_1, test, [IMPL_EXTR_1]
"""A C or C++ marker that attachment rule 7 places on nothing -- alone on its line,
outside a function's body, directly above a preprocessor conditional's line -- is
warned about: one ``marker_above_conditional`` warning per marker, at its line, typed as
the marker (``analyse.rst``, rule 7). Every other marker on nothing, and every marker the
rule does not reach, stays silent.

The analyser cases run ``SourceAnalyse`` on one file; the build cases build a copy of
``doc_test/need_id_refs`` (see ``test_need_id_refs``), whose ``index`` traces the whole of
project ``src``, with ``src/refs.cpp`` reduced to one reference that resolves.
"""

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sphinx_codelinks.analyse.analyse import (
    ABOVE_CONDITIONAL_MSG,
    AnalyseWarning,
    SourceAnalyse,
)
from sphinx_codelinks.analyse.models import WarningSubTypeEnum
from sphinx_codelinks.cmd import app as cli
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig
from sphinx_needs_testkit import assert_no_warnings, build_warnings

from .test_config_only_refs import NO_DIRECTIVE
from .test_need_id_refs import _SHOWS_WARNING_TYPES, _build, _json, _MakeApp, _project

#: The message, as both implementations of the attachment rules emit it
MSG = (
    "directly above a preprocessor conditional, so attached to no entity: "
    "put the marker inside the arm, above the definition"
)

SUB_TYPE = "marker_above_conditional"

#: A one-arm conditional, the line right after the marker in most cases
ARM = "#if FEATURE_B\nvoid active() {}\n#endif\n"


def _analyse(
    tmp_path: Path, source: str, *, preprocessor: PreprocessorConfig | None = None
) -> SourceAnalyse:
    """Every extractor run over ``source``, written to ``x.cpp``."""
    path = tmp_path / "x.cpp"
    path.write_text(source, encoding="utf-8")
    config = SourceAnalyseConfig(
        src_files=[path],
        src_dir=tmp_path,
        get_oneline_needs=True,
        get_need_id_refs=True,
        get_multiline_needs=True,
        preprocessor=preprocessor,
    )
    analyse = SourceAnalyse(config)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return analyse


def _above(analyse: SourceAnalyse) -> list[tuple[int, str]]:
    """The ``(lineno, type)`` of each ``marker_above_conditional`` warning, sorted."""
    return sorted(
        (warning.lineno, warning.type)
        for warning in analyse.warnings
        if warning.sub_type == SUB_TYPE
    )


def test_the_message_is_the_shared_one() -> None:
    """The text is a contract with the other implementation of the attachment rules,
    byte for byte, and the sub-type is a ``WarningSubTypeEnum`` member."""
    assert ABOVE_CONDITIONAL_MSG == MSG
    assert WarningSubTypeEnum.marker_above_conditional.value == SUB_TYPE


def test_a_one_line_need_warns_with_every_field(tmp_path: Path) -> None:
    """One warning, every field as the other analyser warnings write it: the file, the
    marker's 1-based line, the marker's kind, the sub-type and the shared message."""
    analyse = _analyse(
        tmp_path, "namespace lib {\n// @Above, IMPL_ABOVE, impl, []\n" + ARM + "}\n"
    )

    assert analyse.warnings == [
        AnalyseWarning(str(tmp_path / "x.cpp"), 2, MSG, "need", SUB_TYPE)
    ]
    assert analyse.oneline_needs[0].scope is None


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "class Widget {\n    // @need-ids: REQ_A, REQ_B\n" + ARM + "};\n",
            [(2, "need-id-refs")],
            id="need-id-reference",
        ),
        pytest.param(
            "namespace lib {\n// @need impl: Above\n// :id: IMPL_ML\n// @endneed\n"
            + ARM
            + "}\n",
            [(2, "multiline-need")],
            id="multi-line-need-at-its-open-line",
        ),
        pytest.param(
            "namespace lib {\n/*\n * @First, IMPL_A, impl, []\n"
            " * @Second, IMPL_B, impl, []\n */\n" + ARM + "}\n",
            [(3, "need"), (4, "need")],
            id="two-markers-in-one-comment",
        ),
        pytest.param(
            "namespace lib {\n// @First, IMPL_A, impl, []\n"
            "// @need-ids: REQ_A\n" + ARM + "}\n",
            [(2, "need"), (3, "need-id-refs")],
            id="a-need-and-a-reference-in-one-comment-run",
        ),
        pytest.param(
            "void first() {}\n// @At file level, IMPL_FILE, impl, []\n" + ARM,
            [(2, "need")],
            id="file-level",
        ),
        pytest.param(
            "class Widget {\n#if FEATURE_B\n    void active() {}\n"
            "    // @Above else, IMPL_ELSE, impl, []\n#else\n    void fallback() {}\n"
            "#endif\n};\n",
            [(4, "need")],
            id="above-else",
        ),
    ],
)
def test_each_marker_rule_7_places_on_nothing_warns(
    tmp_path: Path, source: str, expected: list[tuple[int, str]]
) -> None:
    """Every marker kind warns, at its own line, typed as itself: one warning per
    marker, so a comment holding two gives two."""
    assert _above(_analyse(tmp_path, source)) == expected


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            "namespace lib {\nvoid first() {}  // @Trailing, IMPL_T, impl, []\n"
            + ARM
            + "}\n",
            id="trailing",
        ),
        pytest.param(
            "void outer() {\n    // @In the body, IMPL_B, impl, []\n"
            "#if FEATURE_B\n    fast();\n#endif\n}\n",
            id="function-body",
        ),
        pytest.param(
            "namespace lib {\n// @Blank line, IMPL_BL, impl, []\n\n" + ARM + "}\n",
            id="blank-line-between",
        ),
        pytest.param(
            "namespace lib {\n// @Above a define, IMPL_D, impl, []\n"
            "#define FAST 1\nvoid active() {}\n}\n",
            id="define-above",
        ),
        pytest.param(
            "// @File header, IMPL_H, impl, []\n\n" + ARM, id="file-header-comment"
        ),
        pytest.param(
            "void first() {}\n// @At the end, IMPL_E, impl, []\n",
            id="file-level-with-nothing-after",
        ),
        pytest.param(
            "namespace lib {\n#if FEATURE_B\n// @Inside the arm, IMPL_ARM, impl, []\n"
            "void active() {}\n#endif\n}\n",
            id="inside-the-arm",
        ),
    ],
)
def test_a_marker_rule_7_does_not_place_stays_silent(
    tmp_path: Path, source: str
) -> None:
    """No warning where rule 7 does not decide: a trailing marker, one in a function's
    body, one with a blank line or another directive between, and a marker on nothing
    by another rule (a file header, nothing after it at file level)."""
    analyse = _analyse(tmp_path, source)

    assert analyse.all_marked_content
    assert analyse.warnings == []


def test_the_libclang_engine_never_warns(tmp_path: Path) -> None:
    """The libclang engine attaches no marker to an entity, so rule 7 never decides
    there: the marker is extracted, and nothing is warned."""
    pytest.importorskip("clang.cindex")
    analyse = _analyse(
        tmp_path,
        "namespace lib {\n// @Above, IMPL_ABOVE, impl, []\n" + ARM + "}\n",
        preprocessor=PreprocessorConfig(defines=[]),
    )

    assert [need.need["id"] for need in analyse.oneline_needs] == ["IMPL_ABOVE"]
    assert analyse.warnings == []


def test_codelinks_analyse_prints_it(tmp_path: Path) -> None:
    """The CLI prints it in the one shape every analyser warning takes."""
    (tmp_path / "x.cpp").write_text(
        "namespace lib {\n// @Above, IMPL_ABOVE, impl, []\n" + ARM + "}\n",
        encoding="utf-8",
    )
    config = tmp_path / "ubproject.toml"
    config.write_text(
        "[codelinks.projects.p.source_discover]\n"
        'src_dir = "./"\n'
        'comment_type = "cpp"\n'
        "[codelinks.projects.p.analyse]\n"
        "get_oneline_needs = true\n",
        encoding="utf-8",
    )
    outdir = tmp_path / "out"
    outdir.mkdir()

    result = CliRunner().invoke(cli, ["analyse", str(config), "--outdir", str(outdir)])

    assert result.exit_code == 0, result.output
    # rich wraps the console at its width, anywhere in a long path: compare without
    # whitespace
    expected = (
        f"Analyse warning in {tmp_path.resolve() / 'x.cpp'}:2 - {SUB_TYPE}: {MSG}"
    )
    assert re.sub(r"\s+", "", expected) in re.sub(r"\s+", "", result.output)


#: ``refs.cpp`` with nothing to warn about
REFS = {"src/refs.cpp": "// @need-ids: REQ_001\nvoid implements_a() {}\n"}

#: line 2 is a one-line need directly above a conditional in a namespace
ABOVE = {"src/x.cpp": "namespace lib {\n// @Above, IMPL_ABOVE\n" + ARM + "}\n"}


def test_the_build_warns_at_the_marker_s_line(
    tmp_path: Path, make_app: _MakeApp
) -> None:
    """One warning at the file and line, the sub-type leading the message, typed
    ``codelinks.marker_above_conditional``; the need is still created, on no entity."""
    _project(tmp_path, files={**REFS, **ABOVE})
    app = _build(tmp_path, make_app)

    suffix = " [codelinks.marker_above_conditional]" if _SHOWS_WARNING_TYPES else ""
    assert app.statuscode == 0
    assert build_warnings(app) == [
        f"src/x.cpp:2: WARNING: {SUB_TYPE}: {MSG}{suffix}"
    ]
    assert "IMPL_ABOVE" in _json(app)["needs"]


def test_suppress_warnings_silences_it(tmp_path: Path, make_app: _MakeApp) -> None:
    """Its own ``suppress_warnings`` entry silences it, and ``codelinks.oneline`` does
    not: the two are separate sub-types."""
    _project(tmp_path, files={**REFS, **ABOVE})
    app = _build(
        tmp_path,
        make_app,
        confoverrides={"suppress_warnings": ["codelinks.marker_above_conditional"]},
    )

    assert_no_warnings(app)
    assert "IMPL_ABOVE" in _json(app)["needs"]


def test_a_config_only_project_reports_none(tmp_path: Path, make_app: _MakeApp) -> None:
    """A project no directive traces reports no analyser warning, this one included."""
    _project(tmp_path, files={**REFS, **NO_DIRECTIVE, **ABOVE})
    app = _build(tmp_path, make_app)

    assert_no_warnings(app)
