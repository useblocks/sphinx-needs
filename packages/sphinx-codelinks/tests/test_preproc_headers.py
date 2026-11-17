"""A header is read through every compilation-database entry that includes it
(useblocks/ubcode#4866).

A compilation database lists translation units, never headers. A header it does not
list is read through each entry whose parse includes it, at any depth (a unit): each
unit contributes the ranges it skipped in the header's first inclusion, or the header
as written (an unguarded header two directives include, an unknown target, every parse
refused), and the header leaves out only what every unit skipped. The shared cases of
``tests/data/extraction/preproc_compile_db.yaml`` pin the extraction; these tests pin
the pieces, the memo and the run.
"""

import json
import os
import pickle
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import compile_db, libclang_parser
from sphinx_codelinks.analyse.preproc.headers import (
    REFUSED,
    REPEATED,
    UNKNOWN,
    Contribution,
    ContributionKind,
    SkippedSpan,
    UnitKey,
    UnitRecord,
    contribution,
    intersect,
    lexical_closure,
    skipped,
    union_of_arms,
    wholly_skipped,
)
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig

from .test_need_id_refs import _build, _json, _project
from .test_preproc_includer import UNITY_PROJECT, _RecordingLogger


def _span(start: int, end: int) -> SkippedSpan:
    """A span from byte ``start`` to ``end``, on lines ``start // 10 + 1`` to
    ``end // 10 + 1``."""
    return SkippedSpan(start, end, start // 10 + 1, end // 10 + 1)


def _spans(ranges: list[tuple[int, int]]) -> list[SkippedSpan]:
    return [_span(start, end) for start, end in ranges]


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        pytest.param([(0, 10)], [(20, 30)], [], id="disjoint"),
        pytest.param([(0, 10)], [(10, 30)], [], id="touching"),
        pytest.param([(0, 50)], [(10, 20)], [(10, 20)], id="nested"),
        pytest.param(
            [(0, 10), (30, 40)],
            [(0, 10), (30, 40)],
            [(0, 10), (30, 40)],
            id="identical",
        ),
        pytest.param([], [(0, 10)], [], id="empty-left"),
        pytest.param([(0, 10)], [], [], id="empty-right"),
        pytest.param([(0, 25)], [(15, 40)], [(15, 25)], id="partial"),
        pytest.param([(0, 25)], [(20, 45)], [(20, 25)], id="chain"),
        pytest.param(
            [(0, 100)],
            [(5, 15), (30, 40), (90, 120)],
            [(5, 15), (30, 40), (90, 100)],
            id="one-over-many",
        ),
    ],
)
def test_the_intersection_keeps_what_both_sides_skip(
    left: list[tuple[int, int]],
    right: list[tuple[int, int]],
    expected: list[tuple[int, int]],
) -> None:
    """A disjoint pair gives nothing (touching ranges share no byte), a nested one the
    inner range, identical ones themselves; an empty side gives nothing; and an
    ``#if``/``#elif`` chain whose units take different arms keeps only the directive
    between them (the ``#elif`` keyword both ranges hold), never an arm one of them
    compiles. Either side first."""
    assert intersect(_spans(left), _spans(right)) == _spans(expected)
    assert intersect(_spans(right), _spans(left)) == _spans(expected)


def test_an_intersection_takes_the_lines_of_its_ends() -> None:
    """The line of each end is the line of the range that end came from."""
    one = SkippedSpan(10, 90, 2, 9)
    other = SkippedSpan(40, 120, 5, 12)
    assert intersect([one], [other]) == [SkippedSpan(40, 90, 5, 9)]


@pytest.mark.parametrize(
    ("contributions", "expected"),
    [
        pytest.param(
            [skipped(_spans([(30, 40), (0, 10)]))], [(0, 10), (30, 40)], id="one"
        ),
        pytest.param(
            [
                skipped(_spans([(0, 10), (30, 40)])),
                skipped(_spans([(30, 40), (50, 60)])),
            ],
            [(30, 40)],
            id="two",
        ),
        pytest.param(
            [
                skipped(_spans([(0, 50)])),
                skipped(_spans([(10, 40)])),
                skipped(_spans([(20, 30)])),
            ],
            [(20, 30)],
            id="three-nested",
        ),
        pytest.param([skipped(_spans([(0, 10)])), REPEATED], [], id="repeated"),
        pytest.param([UNKNOWN, skipped(_spans([(0, 10)]))], [], id="unknown"),
        pytest.param([skipped(_spans([(0, 10)])), REFUSED], [], id="refused"),
        pytest.param([], [], id="none"),
    ],
)
def test_the_union_of_arms(
    contributions: list[Contribution], expected: list[tuple[int, int]]
) -> None:
    """One unit that reads the header as written keeps every arm, whatever the others
    skip; with none, the ranges every unit skipped; a single unit's own, sorted."""
    assert union_of_arms(contributions) == _spans(expected)


@pytest.mark.parametrize(
    ("later", "repeated"),
    [
        pytest.param([], False, id="entered-once"),
        pytest.param([True], False, id="guarded-entered-twice"),
        pytest.param([True, True], False, id="guarded-entered-thrice"),
        pytest.param([False], True, id="unguarded-entered-twice"),
        pytest.param([True, False], True, id="unguarded-entered-thrice"),
    ],
)
def test_the_contribution_of_a_known_target(later: list[bool], repeated: bool) -> None:
    """A unit whose target is known reads a header in its first inclusion's ranges when
    it enters the header once, or when every later entry skips it whole (a guard whose
    macro the first entry defined: that one decides); a header a later entry compiles
    again (an X-macro header, or a whole-file ``#ifndef`` wrapper whose macro nothing
    defines), as written. ``later`` says, per later entry, whether it is wholly
    skipped."""
    first = _spans([(0, 10)])
    expected = REPEATED if repeated else skipped(first)
    assert contribution(later, first) == expected


@pytest.mark.parametrize(
    ("code", "ranges", "expected"),
    [
        pytest.param([0, 5, 20], [(0, 25)], True, id="every-token-inside"),
        pytest.param([0, 5, 20], [(0, 10), (15, 25)], True, id="across-two-ranges"),
        pytest.param([0, 12, 20], [(0, 10), (15, 25)], False, id="one-between"),
        pytest.param([0, 30], [(0, 25)], False, id="one-after"),
        pytest.param([], [], True, id="no-code-at-all"),
        pytest.param([0], [], False, id="no-range"),
    ],
)
def test_an_entry_is_wholly_skipped_when_its_ranges_hold_every_token(
    code: list[int], ranges: list[tuple[int, int]], expected: bool
) -> None:
    """A later entry of a file is wholly skipped when every token of the file but its
    comments starts inside one of the entry's skipped ranges (bounds included: a range
    runs from a directive's ``#`` to the end of the closing keyword)."""
    assert wholly_skipped(code, ranges) is expected


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_the_lexical_closure_follows_every_include_line(tmp_path: Path) -> None:
    """What a unit whose arms no parse decides may include: the files its ``#include``
    lines name, at any depth, through its include path, one in an ``#if`` arm too, a
    cycle followed once, and only files ``keep`` keeps (a system header the path does
    not find names nothing); never the main file itself."""
    root = tmp_path.resolve()
    _write(
        root,
        {
            "main.c": (
                '#ifdef __XTENSA__\n#include "a.h"\n#endif\n#include <b.h>\n'
                '#include <stdio.h>\n#include "main.c"\n#include "../outside.h"\n'
            ),
            "a.h": '#include "inc/c.h"\n',
            "inc/b.h": "",
            "inc/c.h": '#include "../a.h"\n',
        },
    )
    (root.parent / "outside.h").write_text("", encoding="utf-8")
    args = [f"{compile_db.WORKING_DIRECTORY_FLAG}{root}", "-Iinc"]
    closure = lexical_closure(
        root / "main.c", args, lambda path: path.is_relative_to(root)
    )
    assert closure == {root / "a.h", root / "inc" / "b.h", root / "inc" / "c.h"}


def test_a_parse_contributes_by_what_each_entry_compiles(tmp_path: Path) -> None:
    """A known-target parse's contribution to each project file it includes: a guarded
    header (``#ifndef`` or ``#pragma once``) its skipped ranges however many directives
    name it (a ``-include`` is one), an unguarded one entered once its ranges, an
    unguarded one entered twice as written, and so is one whose whole-file ``#ifndef``
    wrapper names a macro nothing defines (``clang_isFileMultipleIncludeGuarded`` calls
    it guarded, yet each entry compiles it again); a file outside the root, none. (An
    unguarded file whose later entries compile nothing, ``#if 0`` alone, would keep its
    ranges: the first entry decides as well as any.)"""
    root = tmp_path.resolve() / "project"
    _write(
        root,
        {
            "main.c": (
                '#include "g.h"\n#include "g.h"\n#include "x.h"\n#include "x.h"\n'
                '#include "p.h"\n#include "u.h"\n#include "../outside.h"\n'
                '#include "w.h"\n#include "w.h"\n'
            ),
            "g.h": "#ifndef G_H\n#define G_H\n#if 0\nint g;\n#endif\n#endif\n",
            "x.h": "#if 0\nint x;\n#endif\nX(1)\n",
            "p.h": "#pragma once\n#if 0\nint p;\n#endif\n",
            "u.h": "#if 0\nint u;\n#endif\n",
            "w.h": "#ifndef W_OFF\n#if 0\nint w;\n#endif\n#endif\n",
        },
    )
    (root.parent / "outside.h").write_text("", encoding="utf-8")
    args = [f"{compile_db.WORKING_DIRECTORY_FLAG}{root}", "-include", "p.h"]
    main = root / "main.c"
    tu = libclang_parser.parse_translation_unit(main, args)

    contributions = libclang_parser.unit_contributions(
        tu, root, main, lambda path: path.is_relative_to(root)
    )

    kinds = {path.name: each.kind for path, each in contributions.items()}
    assert kinds == {
        "g.h": ContributionKind.skipped,
        "x.h": ContributionKind.repeated,
        "p.h": ContributionKind.skipped,
        "u.h": ContributionKind.skipped,
        "w.h": ContributionKind.repeated,
    }
    lines = {
        path.name: [(span.start_line, span.end_line) for span in each.ranges]
        for path, each in contributions.items()
    }
    assert lines["g.h"] == [(3, 5)]
    assert lines["p.h"] == [(2, 4)]
    assert lines["u.h"] == [(1, 3)]
    # the raw byte offsets of the range, from the `#if`'s `#` to the end of `endif`
    (span,) = contributions[root / "u.h"].ranges
    text = (root / "u.h").read_bytes()
    assert (span.start_byte, span.end_byte) == (0, text.index(b"endif") + len(b"endif"))


def _db(root: Path, entries: list[dict], name: str = "compile_commands.json") -> Path:
    db = root / name
    db.parent.mkdir(parents=True, exist_ok=True)
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(root / e.get("directory", ".")),
                    "file": e["file"],
                    "arguments": [
                        e.get("compiler", "clang"),
                        *e["args"],
                        "-c",
                        e["file"],
                    ],
                }
                for e in entries
            ]
        ),
        encoding="utf-8",
    )
    return db


def _analyse(
    root: Path,
    analysed: list[str],
    db: Path | None,
    *,
    src_dir: Path | None = None,
    memo: dict[UnitKey, UnitRecord] | None = None,
) -> SourceAnalyse:
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[root / name for name in analysed],
            src_dir=src_dir or root,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            preprocessor=PreprocessorConfig(compile_commands=db, std="c11"),
        ),
        unit_memo=memo,
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return analyse


def _ids(analyse: SourceAnalyse) -> set[str]:
    return {n.need["id"] for n in analyse.oneline_needs}


#: a header three ``#ifdef`` arms deep, and a fourth no unit compiles
HEADER = (
    "#pragma once\n// @base, IMPL_BASE, impl\n"
    "#ifdef ONE\n// @one, IMPL_ONE, impl\n#endif\n"
    "#ifdef TWO\n// @two, IMPL_TWO, impl\n#endif\n"
    "#ifdef NEVER_SET\n// @never, IMPL_NEVER, impl\n#endif\n"
)


@pytest.fixture
def parsed_units(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The main files of the units the analysis parses (each memo miss), by name."""
    parsed: list[str] = []
    real = SourceAnalyse._parse_unit

    def spy(self: SourceAnalyse, key: UnitKey, *args: object) -> UnitRecord:
        parsed.append(key.main.name)
        return real(self, key, *args)

    monkeypatch.setattr(SourceAnalyse, "_parse_unit", spy)
    return parsed


def _later(path: Path) -> None:
    later = path.stat().st_mtime + 10
    os.utime(path, (later, later))


def test_a_unit_is_parsed_again_only_when_its_files_change(
    tmp_path: Path, parsed_units: list[str]
) -> None:
    """Two analyses sharing one memo: the second parses no unit; touching one entry's
    main file parses that unit alone again; touching the header, which both units
    include, parses both again; the header's read follows each time."""
    _write(
        tmp_path,
        {"a.c": '#include "case.h"\n', "b.c": '#include "case.h"\n', "case.h": HEADER},
    )
    db = _db(
        tmp_path,
        [{"file": "a.c", "args": ["-DONE"]}, {"file": "b.c", "args": ["-DTWO"]}],
    )
    memo: dict[UnitKey, UnitRecord] = {}
    expected = {"IMPL_BASE", "IMPL_ONE", "IMPL_TWO"}

    assert _ids(_analyse(tmp_path, ["case.h"], db, memo=memo)) == expected
    assert sorted(parsed_units) == ["a.c", "b.c"]
    assert {key.main.name for key in memo} == {"a.c", "b.c"}

    parsed_units.clear()
    assert _ids(_analyse(tmp_path, ["case.h"], db, memo=memo)) == expected
    assert parsed_units == []

    (tmp_path / "a.c").write_text('#define NEVER_SET\n#include "case.h"\n')
    _later(tmp_path / "a.c")
    assert _ids(_analyse(tmp_path, ["case.h"], db, memo=memo)) == {
        *expected,
        "IMPL_NEVER",
    }
    assert parsed_units == ["a.c"]

    parsed_units.clear()
    _later(tmp_path / "case.h")
    _analyse(tmp_path, ["case.h"], db, memo=memo)
    assert sorted(parsed_units) == ["a.c", "b.c"]


def test_an_entry_the_database_drops_leaves_the_memo(
    tmp_path: Path, parsed_units: list[str]
) -> None:
    """A unit whose entry is no longer in the database is dropped from the memo, and
    no longer counts: the header follows the one entry left."""
    _write(
        tmp_path,
        {"a.c": '#include "case.h"\n', "b.c": '#include "case.h"\n', "case.h": HEADER},
    )
    db = _db(
        tmp_path,
        [{"file": "a.c", "args": ["-DONE"]}, {"file": "b.c", "args": ["-DTWO"]}],
    )
    memo: dict[UnitKey, UnitRecord] = {}
    _analyse(tmp_path, ["case.h"], db, memo=memo)

    db = _db(tmp_path, [{"file": "a.c", "args": ["-DONE"]}])
    assert _ids(_analyse(tmp_path, ["case.h"], db, memo=memo)) == {
        "IMPL_BASE",
        "IMPL_ONE",
    }
    assert {key.main.name for key in memo} == {"a.c"}


def test_every_entry_of_a_file_compiled_twice_counts(tmp_path: Path) -> None:
    """Two entries for one ``.c`` file, with different ``-D``: each is a unit, so the
    header keeps the arms of both (the ``.c`` file's own read keeps one entry)."""
    _write(tmp_path, {"a.c": '#include "case.h"\n', "case.h": HEADER})
    db = _db(
        tmp_path,
        [{"file": "a.c", "args": ["-DONE"]}, {"file": "a.c", "args": ["-DTWO"]}],
    )
    analyse = _analyse(tmp_path, ["case.h"], db)
    assert _ids(analyse) == {"IMPL_BASE", "IMPL_ONE", "IMPL_TWO"}
    assert sorted(key.ordinal for key in analyse.unit_memo) == [0, 1]


def test_an_entry_outside_the_source_directory_counts(tmp_path: Path) -> None:
    """The entry's main file lives in the build directory, outside the analysed source
    directory: it is a unit all the same, and the header it includes is read through
    it."""
    root = tmp_path.resolve()
    _write(
        root,
        {"build/main.c": '#include "case.h"\n', "src/case.h": HEADER},
    )
    db = _db(
        root, [{"file": "main.c", "directory": "build", "args": ["-I../src", "-DONE"]}]
    )
    analyse = _analyse(root, ["src/case.h"], db, src_dir=root / "src")
    assert _ids(analyse) == {"IMPL_BASE", "IMPL_ONE"}
    assert root / "build" / "main.c" in analyse.dependencies


def test_a_header_with_no_database_of_its_own_reads_the_analysis_databases(
    tmp_path: Path,
) -> None:
    """The walk-up from the header finds no database (it stops at the source
    directory); the analysis' ``.c`` file finds one in its own directory: the header is
    read through that database's entries."""
    root = tmp_path.resolve()
    _write(
        root,
        {"build/main.c": '#include "../inc/case.h"\n', "inc/case.h": HEADER},
    )
    _db(root / "build", [{"file": "main.c", "args": ["-DTWO"]}])
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[root / "build" / "main.c", root / "inc" / "case.h"],
            src_dir=root,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(std="c11"),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    assert _ids(analyse) == {"IMPL_BASE", "IMPL_TWO"}


def test_a_header_with_an_entry_of_its_own_keeps_its_read(tmp_path: Path) -> None:
    """A header the database lists (a ``-x c-header`` entry) is read with its own
    arguments, not through the entries that include it."""
    _write(tmp_path, {"a.c": '#include "case.h"\n', "case.h": HEADER})
    db = _db(
        tmp_path,
        [
            {"file": "a.c", "args": ["-DONE"]},
            {"file": "case.h", "args": ["-x", "c-header", "-DTWO"]},
        ],
    )
    assert _ids(_analyse(tmp_path, ["case.h"], db)) == {"IMPL_BASE", "IMPL_TWO"}


def test_a_header_no_entry_includes_keeps_the_defines(tmp_path: Path) -> None:
    """No entry includes the header (``no_includer``): it is read with the
    ``[preprocessor]`` defines, as before."""
    _write(tmp_path, {"a.c": "int a;\n", "case.h": HEADER})
    db = _db(tmp_path, [{"file": "a.c", "args": ["-DONE"]}])
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[tmp_path / "case.h"],
            src_dir=tmp_path,
            get_oneline_needs=True,
            preprocessor=PreprocessorConfig(
                compile_commands=db, defines=["TWO"], std="c11"
            ),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    assert _ids(analyse) == {"IMPL_BASE", "IMPL_TWO"}


def test_an_unknown_target_unit_contributes_its_host_and_lexical_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry built for xtensa, which libclang does not model: its target unknown, it
    reads as written both the header only its ``#ifdef __XTENSA__`` arm includes (its
    ``#include`` lines) and the one it names through a macro (a parse for the host), each
    with one ``preprocessor_target_unknown`` warning, every arm kept."""
    _write(
        tmp_path,
        {
            "main.c": (
                '#ifdef __XTENSA__\n#include "x.h"\n#endif\n'
                '#define NAMED "y.h"\n#include NAMED\n'
            ),
            "x.h": "#pragma once\n#ifdef NEVER_SET\n// @x, IMPL_X, impl\n#endif\n",
            "y.h": "#pragma once\n#ifdef NEVER_SET\n// @y, IMPL_Y, impl\n#endif\n",
        },
    )
    db = _db(
        tmp_path, [{"file": "main.c", "compiler": "xtensa-esp32-elf-gcc", "args": []}]
    )
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)

    analyse = _analyse(tmp_path, ["x.h", "y.h"], db)

    assert _ids(analyse) == {"IMPL_X", "IMPL_Y"}
    (record,) = analyse.unit_memo.values()
    assert record.triple is None
    assert {path.name: each for path, each in record.contributions.items()} == {
        "x.h": UNKNOWN,
        "y.h": UNKNOWN,
    }
    assert [subtype for _, subtype in recorder.warnings] == [
        "preprocessor_target_unknown",
        "preprocessor_target_unknown",
    ]


def test_a_refused_unit_contributes_its_lexical_closure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An entry whose every parse libclang refuses (a ``-std`` it does not know): no
    parse decides an arm, so the header its ``#include`` lines name is read as written,
    with one ``preprocessor_parse_refused`` warning naming the includer."""
    _write(tmp_path, {"main.c": '#include "case.h"\n', "case.h": HEADER})
    db = _db(tmp_path, [{"file": "main.c", "args": ["-std=gnu2y", "-DONE"]}])
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)

    analyse = _analyse(tmp_path, ["case.h"], db)

    assert _ids(analyse) == {"IMPL_BASE", "IMPL_ONE", "IMPL_TWO", "IMPL_NEVER"}
    (record,) = analyse.unit_memo.values()
    assert record.contributions == {(tmp_path / "case.h").resolve(): REFUSED}
    ((message, subtype),) = recorder.warnings
    assert subtype == "preprocessor_parse_refused"
    assert f"its includer {(tmp_path / 'main.c').resolve()}" in message


def test_the_reader_is_the_unit_that_includes_the_most_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Of the units with a known target, the one that includes the most project files
    reads the header (``z.c`` here, though ``a.c`` sorts first), parsed again once for
    both headers it reads."""
    _write(
        tmp_path,
        {
            "a.c": '#include "case.h"\n',
            "z.c": '#include "case.h"\n#include "other.h"\n',
            "case.h": HEADER,
            "other.h": "#pragma once\n// @other, IMPL_OTHER, impl\n",
        },
    )
    db = _db(
        tmp_path,
        [{"file": "a.c", "args": ["-DONE"]}, {"file": "z.c", "args": ["-DTWO"]}],
    )
    parsed: list[str] = []
    real = libclang_parser.parse_translation_unit

    def counting(file_path: Path, args: list[str]) -> object:
        parsed.append(file_path.name)
        return real(file_path, args)

    monkeypatch.setattr(libclang_parser, "parse_translation_unit", counting)

    analyse = _analyse(tmp_path, ["case.h", "other.h"], db)

    assert _ids(analyse) == {"IMPL_BASE", "IMPL_ONE", "IMPL_TWO", "IMPL_OTHER"}
    # each unit once, then the reader once again
    assert parsed == ["a.c", "z.c", "z.c"]


def test_a_header_depends_on_every_unit_and_what_it_includes(tmp_path: Path) -> None:
    """The header's analysis records the database, every entry's main file (one that
    does not include it too: an edit can make it) and every project file each
    includes."""
    _write(
        tmp_path,
        {
            "a.c": '#include "case.h"\n#include "flags.h"\n',
            "b.c": "int b;\n",
            "case.h": HEADER,
            "flags.h": "",
        },
    )
    db = _db(tmp_path, [{"file": "a.c", "args": []}, {"file": "b.c", "args": []}])
    analyse = _analyse(tmp_path, ["case.h"], db)
    assert analyse.dependencies == {
        (tmp_path / name).resolve()
        for name in ("compile_commands.json", "a.c", "b.c", "case.h", "flags.h")
    }


#: the unity project, with a header in ``src`` that only a second entry includes
HEADER_PROJECT = {
    "toml_extra": UNITY_PROJECT["toml_extra"],
    "files": {
        **UNITY_PROJECT["files"],
        "build/compile_commands.json": json.dumps(
            [
                *json.loads(UNITY_PROJECT["files"]["build/compile_commands.json"]),
                {
                    "directory": ".",
                    "file": "hmain.c",
                    "arguments": ["clang", "-I../src", "-DH_FLAG", "-c", "hmain.c"],
                },
            ]
        ),
        "build/hmain.c": '#include "h.h"\n',
        "src/h.h": (
            "#pragma once\n#ifdef H_FLAG\n// @h on, IMPL_H_ON, impl\n"
            "#else\n// @h off, IMPL_H_OFF, impl\n#endif\n"
        ),
    },
}


def test_an_edit_to_an_entry_that_includes_a_header_reads_it_again(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """The entry that includes the traced header lives in the build directory, outside
    every scope, and nothing else reads through it: an edit to it still reads the
    directive's document again, and the header's needs follow the edit."""
    _project(tmp_path, **HEADER_PROJECT)
    app = _build(tmp_path, make_app)
    needs = _json(app)["needs"]
    assert "IMPL_H_ON" in needs
    assert "IMPL_H_OFF" not in needs

    hmain = tmp_path / "build" / "hmain.c"
    hmain.write_text('#undef H_FLAG\n#include "h.h"\n', encoding="utf-8")
    _later(hmain)
    app = _build(tmp_path, make_app, freshenv=False)

    needs = _json(app)["needs"]
    assert "IMPL_H_OFF" in needs
    assert "IMPL_H_ON" not in needs


def test_the_environment_keeps_what_each_entry_contributes(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """The units a build parsed are kept in its environment, so the next build parses
    none whose files did not change."""
    _project(tmp_path, **HEADER_PROJECT)
    app = _build(tmp_path, make_app)
    pickled = Path(app.doctreedir, "environment.pickle")
    env = pickle.loads(pickled.read_bytes())
    store = env.codelinks_header_units
    assert {key.main.name for key in store} == {"unity.cpp", "hmain.c"}
    hmain = next(record for key, record in store.items() if key.main.name == "hmain.c")
    assert [path.name for path in hmain.contributions] == ["h.h"]


def test_an_environment_pickled_at_env_version_9_is_read_again(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """An environment of ``env_version`` 9 holds records of headers no entry lists read
    with the ``[preprocessor]`` defines alone, where such a header is now read through
    every entry that includes it. Nothing in the sources or the configuration changed:
    ``env_version`` 10 is what has the build discard it and read every document
    again."""
    _project(tmp_path, **HEADER_PROJECT)
    app = _build(tmp_path, make_app)
    pickled = Path(app.doctreedir, "environment.pickle")
    env = pickle.loads(pickled.read_bytes())
    env.version["sphinx_codelinks"] = 9
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    app = _build(tmp_path, make_app, freshenv=False)

    status = strip_colors(app._status.getvalue())
    assert (
        "loading pickled environment... failed: build environment version not current"
        in status
    )


#: an ``#if`` chain inside a whole-file wrapper whose macro nothing defines
WRAPPED = (
    "#ifndef X_DISABLED\n#if PASS == 1\n// @one, IMPL_ONE, impl\n"
    "#elif PASS == 2\n// @two, IMPL_TWO, impl\n#endif\n#endif\n"
)


def test_a_wrapper_that_guards_nothing_is_read_as_written(tmp_path: Path) -> None:
    """``x.h`` is wrapped in ``#ifndef X_DISABLED``, which libclang reports as an include
    guard, but nothing defines ``X_DISABLED``: ``main.c`` enters it twice and compiles
    the ``PASS == 1`` arm, then the ``PASS == 2`` one. Neither is left out."""
    _write(
        tmp_path,
        {
            "main.c": (
                '#define PASS 1\n#include "x.h"\n#undef PASS\n#define PASS 2\n'
                '#include "x.h"\n'
            ),
            "x.h": WRAPPED,
        },
    )
    db = _db(tmp_path, [{"file": "main.c", "args": []}])
    assert _ids(_analyse(tmp_path, ["x.h"], db)) == {"IMPL_ONE", "IMPL_TWO"}


def test_the_lexical_closure_starts_at_the_forced_includes(tmp_path: Path) -> None:
    """The lexical closure of a unit no parse reads begins with its ``-include`` and
    ``-imacros`` files (the working directory first, then the search path), follows
    ``#include_next``, and goes through files outside the project (an SDK header on the
    search path that includes a project header), keeping only the project's."""
    root = tmp_path.resolve() / "project"
    sdk = tmp_path.resolve() / "sdk"
    _write(
        tmp_path,
        {
            "project/main.c": "int a;\n",
            "project/forced.h": "",
            "project/inc/macros.h": "",
            "project/inc/cfg.h": "#include_next <cfg.h>\n",
            "project/inc2/cfg.h": "#include <sdk.h>\n",
            "sdk/sdk.h": '#include "board.h"\n',
            "project/board/board.h": "",
        },
    )
    args = [
        f"{compile_db.WORKING_DIRECTORY_FLAG}{root}",
        "-include",
        "forced.h",
        "-imacrosmacros.h",
        "-include",
        "cfg.h",
        "-Iinc",
        "-Iinc2",
        f"-I{sdk}",
        "-Iboard",
    ]
    closure = lexical_closure(
        root / "main.c", args, lambda path: path.is_relative_to(root)
    )
    assert closure == {
        root / "forced.h",
        root / "inc" / "macros.h",
        root / "inc" / "cfg.h",
        root / "inc2" / "cfg.h",
        root / "board" / "board.h",
    }


def test_a_refused_unit_reads_its_forced_include_as_written(tmp_path: Path) -> None:
    """``a.c`` names ``case.h`` only through ``-include``, and libclang refuses every
    parse of it (``-mfpmath=vfp`` on the host): its contribution is ``case.h`` as
    written, so the arm ``b.c`` skips and ``a.c`` compiles (``-DFEATURE_A``) is kept."""
    _write(
        tmp_path,
        {
            "a.c": "int a;\n",
            "b.c": '#include "case.h"\n',
            "case.h": "#pragma once\n#ifdef FEATURE_A\n// @a, IMPL_A, impl\n#endif\n",
        },
    )
    db = _db(
        tmp_path,
        [
            {
                "file": "a.c",
                "compiler": "gcc",
                "args": ["-mfpmath=vfp", "-DFEATURE_A", "-include", "case.h"],
            },
            {"file": "b.c", "args": []},
        ],
    )
    assert _ids(_analyse(tmp_path, ["case.h"], db)) == {"IMPL_A"}


def test_a_header_read_without_the_refused_flags_is_warned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The only entry that includes ``case.h`` is read for its target without the
    ``-march``/``-mabi`` libclang refused, which decide ``__ARM_FEATURE_AES``: the arm
    is left out as that parse decides, and the header is warned as the ``.c`` file would
    be, worded for its includer."""
    _write(
        tmp_path,
        {
            "a.c": '#include "case.h"\n',
            "case.h": (
                "#pragma once\n// @base, IMPL_BASE, impl\n"
                "#ifdef __ARM_FEATURE_AES\n// @aes, IMPL_AES, impl\n#endif\n"
            ),
        },
    )
    db = _db(
        tmp_path,
        [
            {
                "file": "a.c",
                "args": [
                    "--target=aarch64-linux-gnu",
                    "-march=armv8.2-a+crypto",
                    "-mabi=lp64",
                ],
            }
        ],
    )
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)

    assert _ids(_analyse(tmp_path, ["case.h"], db)) == {"IMPL_BASE"}

    ((message, subtype),) = recorder.warnings
    assert subtype == "preprocessor_target_unknown"
    assert message.startswith(f"codelinks: {tmp_path / 'case.h'} is read for aarch64")
    assert "`-march=armv8.2-a+crypto`" in message
    assert "its includer" in message
