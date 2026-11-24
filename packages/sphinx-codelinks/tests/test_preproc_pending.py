# @Test the rediscovery of includes a parse could not resolve, TEST_PREPROC_PENDING_1, test, [IMPL_PREPROC_1]
"""A parse made before an included file existed goes stale when the file appears
(useblocks/sphinx-needs#2584).

With the preprocessor-aware engine, a ``#include`` libclang reports as ``'x' file
not found`` leaves no trace in what a build watches: ``SourceAnalyse.dependencies``
holds the compile database, the main files and the files the parse FOUND. So a
parse of a tree indexed before a generated header's first build stays "fresh"
when the header appears, and the code behind it (an ``#ifdef`` arm its macros
decide) stays hidden. These tests pin the places a parse's unresolved includes
are watched: every candidate path the compiler's lookup would have found the name
at, in search order; an ``#include_next``'s directories after the one the
including file was found in; a forced include's working directory first; and the
cap that watches the directories' times instead.
"""

import json
from pathlib import Path

import pytest

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import libclang_parser
from sphinx_codelinks.analyse.preproc.headers import UnitRecord
from sphinx_codelinks.analyse.preproc.includer import (
    IncludeDirective,
    SearchPath,
    lookup_directories,
    pending_signature,
)
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig
from sphinx_codelinks.sphinx_extension.rediscovery import (
    pending_changed,
    pending_fingerprint,
)

from .test_need_id_refs import _build, _json, _project
from .test_preproc_includer import _db, _run, _touch, _write


def _lookup(
    name: str,
    including: Path,
    path: SearchPath,
    *,
    angled: bool = False,
    next_: bool = False,
) -> list[Path]:
    return lookup_directories(
        IncludeDirective(name, angled, 1, next=next_), including, path
    )


def test_lookup_directories_search_order(tmp_path: Path) -> None:
    """A quoted or angled name: the including file's directory, then ``-iquote``,
    then the include path -- a failed angled lookup is retried as a quoted one,
    so both forms name the same candidates. An ``#include_next`` continues in the
    directories after the one the including file was found in."""
    main = _touch(tmp_path / "src" / "main.cpp")
    path = SearchPath(
        quote=(tmp_path / "q",), angled=(tmp_path / "i1", tmp_path / "i2")
    )
    expected = [main.parent, tmp_path / "q", tmp_path / "i1", tmp_path / "i2"]
    assert _lookup("x.h", main, path) == expected
    assert _lookup("x.h", main, path, angled=True) == expected

    # an ``#include_next`` in a header found on the first ``-I`` directory:
    # only the directories after it
    header = (tmp_path / "i1" / "next.h").resolve()
    _touch(header)
    directive = IncludeDirective("next.h", angled=True, line=1, next=True)
    assert lookup_directories(directive, header, path) == [tmp_path / "i2"]

    # in a file found on no search directory (a unit's main file), the lookup
    # starts from the beginning, as clang does
    assert lookup_directories(directive, main, path) == expected


def test_pending_signature_keeps_directories_past_the_cap(tmp_path: Path) -> None:
    """Up to the cap each candidate path is watched itself (``None``: it held no
    file); past it the directories' times are kept instead, so a file created
    under one is still seen."""
    few = [tmp_path / "d" / f"{n}.h" for n in range(3)]
    signature = pending_signature(few)
    assert signature == {path.resolve(): None for path in few}

    (tmp_path / "d").mkdir()
    many = [tmp_path / "d" / f"{n}.h" for n in range(200)]
    signature = pending_signature(many)
    assert signature == {
        (tmp_path / "d").resolve(): (tmp_path / "d").stat().st_mtime_ns
    }


def test_pending_signature_counts_files_not_directories(tmp_path: Path) -> None:
    """A directory named like the include does not count -- the compiler's lookup
    skips it -- so a candidate holding one signs as ``None``, exactly like a
    missing one."""
    (tmp_path / "x.h").mkdir()
    assert pending_signature([tmp_path / "x.h"]) == {(tmp_path / "x.h").resolve(): None}


def test_pending_changed_reports_an_appearing_file_only(tmp_path: Path) -> None:
    """The fingerprint is stale once a candidate path is a FILE: a directory
    appearing at one -- or nothing -- leaves it fresh; a watched directory's
    changed time stales it."""
    fingerprint = pending_fingerprint(
        pending_signature([tmp_path / "a" / "x.h", tmp_path / "b" / "y.h"])
    )
    assert not pending_changed(fingerprint)
    # a directory named like the include does not count
    (tmp_path / "a" / "x.h").mkdir(parents=True)
    assert not pending_changed(fingerprint)
    # a file does
    (tmp_path / "b" / "y.h").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "b" / "y.h").write_text("#define Y 1\n", encoding="utf-8")
    assert pending_changed(fingerprint)

    (tmp_path / "w").mkdir()
    watched = pending_fingerprint(
        pending_signature([tmp_path / "w" / f"{n}.h" for n in range(200)])
    )
    assert not pending_changed(watched)
    (tmp_path / "w" / "x.h").write_text("#define X 1\n", encoding="utf-8")
    assert pending_changed(watched)


def test_unresolved_include_paths_names_each_miss(tmp_path: Path) -> None:
    """Every inclusion directive libclang could not resolve (clang keeps
    preprocessing after the first "file not found", so each one is a cursor with
    no included file) names its candidate paths; a resolved include and a
    directive in an ``#if 0`` arm name none."""
    _write(
        tmp_path,
        {
            "main.cpp": (
                '#include "a.h"\n'
                "#include <b.h>\n"
                "#if 0\n"
                '#include "dead.h"\n'
                "#endif\n"
                '#include "ok.h"\n'
            ),
            "ok.h": "",
        },
    )
    args = [
        f"-working-directory={tmp_path}",
        "-std=c++17",
        "-iquote",
        "q",
        "-Ii",
    ]
    tu = libclang_parser.parse_translation_unit(tmp_path / "main.cpp", args)
    pending = libclang_parser.unresolved_include_paths(tu, args)

    expected: dict[Path, int | None] = {}
    for name in ("a.h", "b.h"):
        for directory in (tmp_path, tmp_path / "q", tmp_path / "i"):
            expected[directory.resolve() / name] = None
    assert pending == expected


def test_unresolved_include_paths_covers_include_next_and_forced(
    tmp_path: Path,
) -> None:
    """An ``#include_next`` names the directories after the one the including
    file was found in; a forced include (``-include``), which has no including
    file, names the working directory first."""
    _write(
        tmp_path,
        {
            "main.cpp": '#include "next.h"\n',
            "inc/next.h": '#include_next "next.h"\n',
        },
    )
    args = [
        f"-working-directory={tmp_path}",
        "-std=c++17",
        "-Iinc",
        "-Iinc2",
        "-include",
        "forced.h",
    ]
    tu = libclang_parser.parse_translation_unit(tmp_path / "main.cpp", args)
    pending = libclang_parser.unresolved_include_paths(tu, args)

    assert pending == {
        (tmp_path / "inc2" / "next.h").resolve(): None,
        (tmp_path / "forced.h").resolve(): None,
        (tmp_path / "inc" / "forced.h").resolve(): None,
        (tmp_path / "inc2" / "forced.h").resolve(): None,
    }


def test_a_parse_before_the_include_exists_reads_it_when_it_appears(
    tmp_path: Path,
) -> None:
    """The regression: a marker behind ``#ifdef CFG`` stays hidden while
    ``cfg.h`` is missing, the places it would be found are watched, and the
    analysis reads it the moment the file appears."""
    _write(
        tmp_path,
        {
            "main.cpp": (
                "#include <cfg.h>\n#ifdef CFG\n// @gated, IMPL_GATED, impl\n#endif\n"
            ),
        },
    )
    db = _db(tmp_path, [{"file": "main.cpp", "args": ["-Igen"]}])

    analyse = _run(tmp_path, ["main.cpp"], db)
    assert not analyse.oneline_needs
    # the includer's directory, then the ``-I`` one, watch the name
    assert analyse.pending == {
        (tmp_path / "cfg.h").resolve(): None,
        (tmp_path / "gen" / "cfg.h").resolve(): None,
    }
    assert pending_changed(pending_fingerprint(analyse.pending)) is False

    (tmp_path / "gen").mkdir()
    (tmp_path / "gen" / "cfg.h").write_text("#define CFG 1\n", encoding="utf-8")
    assert pending_changed(pending_fingerprint(analyse.pending)) is True
    analyse = _run(tmp_path, ["main.cpp"], db)
    assert {n.need["id"] for n in analyse.oneline_needs} == {"IMPL_GATED"}


def test_a_unit_record_goes_stale_when_an_unresolved_include_appears(
    tmp_path: Path,
) -> None:
    """A memoized unit record is fresh while its unresolved includes resolve
    nowhere, stale the moment a file sits at one of the paths."""
    record = UnitRecord(
        fingerprint=(),
        main_mtime=0,
        decision=None,
        triple=None,  # type: ignore[arg-type]
    )
    record.pending = (((tmp_path / "inc" / "later.h").resolve(), None),)
    assert record.fresh((), 0)
    (tmp_path / "inc").mkdir()
    (tmp_path / "inc" / "later.h").write_text("", encoding="utf-8")
    assert not record.fresh((), 0)


def test_a_header_read_through_units_watches_its_pending(tmp_path: Path) -> None:
    """A header with no entry of its own is read through every unit that includes
    it (ubcode#4866); an include one of them could not resolve is kept on the
    record the Sphinx env memoizes, so it joins ``SourceAnalyse.pending``."""
    _write(
        tmp_path,
        {
            "unity.cpp": '#include "h.h"\n',
            "h.h": "#include <gen.h>\n#ifdef GEN\n// @gen, IMPL_GEN, impl\n#endif\n",
        },
    )
    db = _db(tmp_path, [{"file": "unity.cpp", "args": ["-Igen"]}])
    memo: dict = {}

    def run() -> SourceAnalyse:
        analyse = SourceAnalyse(
            SourceAnalyseConfig(
                src_files=[tmp_path / "h.h"],
                src_dir=tmp_path,
                get_need_id_refs=False,
                get_oneline_needs=True,
                get_multiline_needs=False,
                preprocessor=PreprocessorConfig(compile_commands=db),
            )
        )
        analyse.git_remote_url = None
        analyse.git_commit_rev = None
        analyse.unit_memo = memo
        analyse.run(log_summary=False)
        return analyse

    analyse = run()
    assert not analyse.oneline_needs
    assert (tmp_path / "gen" / "gen.h").resolve() in analyse.pending
    # the unit record itself watches the miss, so a build that reuses it sees it
    records = list(memo.values())
    assert len(records) == 1
    assert dict(records[0].pending) == analyse.pending

    # when the include appears the record is stale and the next run reads it
    (tmp_path / "gen").mkdir()
    (tmp_path / "gen" / "gen.h").write_text("#define GEN 1\n", encoding="utf-8")
    assert not records[0].fresh(records[0].fingerprint, records[0].main_mtime)
    analyse = run()
    assert {n.need["id"] for n in analyse.oneline_needs} == {"IMPL_GEN"}


def test_an_include_appearing_outside_the_scope_rereads_the_host(
    tmp_path: Path, make_app
) -> None:
    """The end-to-end regression (#2584): a header resolvable only on an include
    directory OUTSIDE the directive's scope appears between builds; the next
    build re-reads the hosting document (no ``-E``) and the marker behind the
    header's define is extracted."""
    src = tmp_path / "src"
    _project(
        tmp_path,
        files={
            "src/main.cpp": (
                "#include <cfg.h>\n#ifdef CFG\n// @gated, IMPL_GATED, impl\n#endif\n"
            ),
            "src/compile_commands.json": json.dumps(
                [
                    {
                        "directory": str(src),
                        "file": "main.cpp",
                        "arguments": [
                            "clang++",
                            "-std=c++17",
                            "-I../inc",
                            "-c",
                            "main.cpp",
                        ],
                    }
                ]
            ),
        },
        toml_extra="\n[codelinks.projects.src.analyse.preprocessor]\n",
    )

    first = _build(tmp_path, make_app)
    assert "IMPL_GATED" not in _json(first)["needs"]

    inc = tmp_path / "inc"
    inc.mkdir()
    (inc / "cfg.h").write_text("#define CFG 1\n", encoding="utf-8")
    app = _build(tmp_path, make_app, freshenv=False)

    # the host was read again and the marker behind the header's define found:
    # before the fix the parse stayed "fresh" and the marker stayed hidden
    assert "IMPL_GATED" in _json(app)["needs"]
