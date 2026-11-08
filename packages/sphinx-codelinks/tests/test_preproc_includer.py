"""A C/C++ source with no compilation-database entry is read through its includer.

A unity ("jumbo") build compiles one entry whose main file ``#include``s other sources,
which then have no entry of their own. Such a source is read through the parse of an
entry whose main file directly includes it: the candidates come from a lexical scan of
each entry's ``#include`` lines, resolved as the compiler resolves them; the includer
is the first by path whose parse confirms the inclusion; it is parsed once per run; and
the source's markers are read from its first inclusion's active arms. A source with no
such entry keeps being skipped, now with a ``codelinks.not_in_compile_database``
warning. The shared cases of ``tests/data/extraction/preproc_compile_db.yaml`` pin the
extraction; these tests pin the pieces and the run.
"""

import json
import pickle
import weakref
from collections.abc import Callable
from pathlib import Path

import pytest
from sphinx.testing.util import SphinxTestApp
from sphinx.util.console import strip_colors

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import libclang_parser, loader
from sphinx_codelinks.analyse.preproc.includer import (
    IncludeDirective,
    SearchPath,
    inclusion_index,
    resolve_include,
    scan_include_directives,
    search_path,
)
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig
from sphinx_needs_testkit import build_warnings

from .test_need_id_refs import _SHOWS_WARNING_TYPES, DANGLING, _build, _json, _project


def _names(text: str) -> list[tuple[str, bool]]:
    return [(d.name, d.angled) for d in scan_include_directives(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param('#include "a.cpp"\n', [("a.cpp", False)], id="quoted"),
        pytest.param("#include <a.h>\n", [("a.h", True)], id="angled"),
        pytest.param(
            '  \t#  \tinclude\t"sub/a.cpp"\n', [("sub/a.cpp", False)], id="whitespace"
        ),
        pytest.param('#include"a.cpp"\n', [("a.cpp", False)], id="no-space"),
        pytest.param(
            '#include "a.cpp" // why\n#include "b.cpp" /* x */\n',
            [("a.cpp", False), ("b.cpp", False)],
            id="trailing-comments",
        ),
        pytest.param(
            '#include "a.cpp"\r\n#include "b.cpp"\r#include "c.cpp"',
            [("a.cpp", False), ("b.cpp", False), ("c.cpp", False)],
            id="crlf-and-cr",
        ),
        pytest.param('#include_next "a.h"\n', [], id="include-next-is-not"),
        pytest.param('#includes "a.h"\n', [], id="longer-word-is-not"),
        pytest.param("#include MACRO\n", [], id="macro-name-is-not"),
        pytest.param('x; #include "a.cpp"\n', [], id="not-at-line-start"),
        pytest.param('// #include "a.cpp"\n', [], id="line-comment"),
        pytest.param(
            '/*\n#include "a.cpp"\n*/\n#include "b.cpp"\n',
            [("b.cpp", False)],
            id="block-comment",
        ),
        pytest.param(
            '#include "a.cpp" /* opens\n#include "b.cpp"\n*/ #include "c.cpp"\n'
            '#include "d.cpp"\n',
            [("a.cpp", False), ("d.cpp", False)],
            id="block-comment-opened-after-a-directive",
        ),
        pytest.param(
            'const char* s = "/*";\n#include "a.cpp"\n',
            [("a.cpp", False)],
            id="comment-opener-in-a-string",
        ),
        pytest.param(
            'char c = \'"\'; /* x */\n#include "a.cpp"\n',
            [("a.cpp", False)],
            id="quote-in-a-char-literal",
        ),
        pytest.param(
            '// a line comment /* is no block\n#include "a.cpp"\n',
            [("a.cpp", False)],
            id="comment-opener-in-a-line-comment",
        ),
        pytest.param(
            '#if 0\n#include "a.cpp"\n#endif\n',
            [("a.cpp", False)],
            id="if-0-is-lexically-a-directive",
        ),
    ],
)
def test_scan_include_directives(text: str, expected: list[tuple[str, bool]]) -> None:
    """A directive line is a ``#`` at the line's start after optional whitespace,
    optional whitespace and the word ``include``, outside block comments; a string,
    character literal or line comment opens no block comment. The scan cannot see
    ``#if`` arms: an ``#if 0`` directive is found, and the parse decides."""
    assert _names(text) == expected


def test_scan_include_directives_reports_lines() -> None:
    text = '/* a\n#include "x.cpp"\n*/\n\n#include <y.h>\n'
    assert scan_include_directives(text) == [IncludeDirective("y.h", True, 5)]


def test_search_path_reads_the_three_kinds_in_both_forms(tmp_path: Path) -> None:
    """``-iquote``, ``-I`` and ``-isystem``, joined or separate, each kind in argument
    order, relative to the working directory; ``-I`` before ``-isystem`` whatever
    their order on the line, as the compiler searches them; other flags ignored."""
    args = [
        f"-working-directory={tmp_path}",
        "-isystem",
        "sys1",
        "-iquote",
        "q1",
        "-Ii1",
        "-include",
        "pre.h",
        "-isysroot",
        "/root",
        "-I",
        "/abs/i2",
        "-iquoteq2",
        "-isystemsys2",
    ]
    assert search_path(args) == SearchPath(
        quote=(tmp_path / "q1", tmp_path / "q2"),
        angled=(
            tmp_path / "i1",
            Path("/abs/i2"),
            tmp_path / "sys1",
            tmp_path / "sys2",
        ),
    )


def _touch(path: Path, text: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_resolve_include_follows_the_compiler_order(tmp_path: Path) -> None:
    """A quoted name: the including file's directory, then ``-iquote``, then ``-I``,
    then ``-isystem``; an angled one skips the first two. The first existing file
    wins, canonical; a name found nowhere resolves to nothing."""
    main = _touch(tmp_path / "src" / "main.cpp")
    for directory in ("src", "q", "i", "s"):
        _touch(tmp_path / directory / f"in_{directory}.h")
        _touch(tmp_path / directory / "all.h")
    _touch(tmp_path / "i" / "in_i_and_s.h")
    _touch(tmp_path / "s" / "in_i_and_s.h")
    path = SearchPath(quote=(tmp_path / "q",), angled=(tmp_path / "i", tmp_path / "s"))

    def resolve(name: str, angled: bool) -> Path | None:
        return resolve_include(IncludeDirective(name, angled, 1), main, path)

    assert resolve("all.h", angled=False) == (tmp_path / "src" / "all.h").resolve()
    assert resolve("all.h", angled=True) == (tmp_path / "i" / "all.h").resolve()
    assert resolve("in_q.h", angled=False) == (tmp_path / "q" / "in_q.h").resolve()
    assert resolve("in_q.h", angled=True) is None
    assert resolve("in_src.h", angled=True) is None
    assert (
        resolve("in_i_and_s.h", angled=True)
        == (tmp_path / "i" / "in_i_and_s.h").resolve()
    )
    assert resolve("in_s.h", angled=False) == (tmp_path / "s" / "in_s.h").resolve()
    assert (
        resolve("../src/in_src.h", angled=True)
        == (tmp_path / "src" / "in_src.h").resolve()
    )
    assert resolve("missing.h", angled=False) is None


def test_inclusion_index_resolves_through_an_include_dir_and_orders_by_path(
    tmp_path: Path,
) -> None:
    """``#include "src/a.cpp"`` from a build directory resolves through the entry's
    relative ``-I..``; the includers of a file are ordered by path, not by the
    database's order; an include in a comment names nothing; an unreadable main file
    includes nothing."""
    source = _touch(tmp_path / "src" / "a.cpp")
    build = tmp_path / "build"
    z = _touch(build / "z_unity.cpp", '#include "src/a.cpp"\n')
    b = _touch(build / "b_unity.cpp", '#include "../src/a.cpp"\n')
    c = _touch(build / "c_unity.cpp", '/* #include "../src/a.cpp" */\n')
    working = f"-working-directory={build}"
    flags = {
        z.resolve(): [working, "-I.."],
        b.resolve(): [working],
        c.resolve(): [working],
        (build / "gone.cpp").resolve(): [working],
    }

    index = inclusion_index(flags)

    assert index == {source.resolve(): [b.resolve(), z.resolve()]}


def _write(root: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        _touch(root / relative, text)


def _db(root: Path, entries: list[dict]) -> Path:
    db = root / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(root / e.get("directory", ".")),
                    "file": e["file"],
                    "arguments": ["clang++", "-std=c++17", *e["args"], "-c", e["file"]],
                }
                for e in entries
            ]
        ),
        encoding="utf-8",
    )
    return db


def _run(
    root: Path, analysed: list[str], db: Path, defines: list[str] | None = None
) -> SourceAnalyse:
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[root / name for name in analysed],
            src_dir=root,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            preprocessor=PreprocessorConfig(compile_commands=db, defines=defines or []),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return analyse


def _ids(analyse: SourceAnalyse) -> set[tuple[str, str]]:
    return {(n.filepath.name, n.need["id"]) for n in analyse.oneline_needs}


class _RecordingLogger:
    """Records the module logger's warnings with their subtype (the real logger is
    slotted, so the module-level one is swapped)."""

    def __init__(self) -> None:
        self.warnings: list[tuple[str, str]] = []

    def warning(self, msg: str, *, subtype: str = "", **_k: object) -> None:
        self.warnings.append((msg, subtype))

    def info(self, *_a: object, **_k: object) -> None:
        pass

    def debug(self, *_a: object, **_k: object) -> None:
        pass


#: a two-file unity layout: unity.cpp, the only entry, includes a.cpp and b.cpp
UNITY = {
    "unity.cpp": (
        '#include "a.cpp"\n#define AFTER_A 1\n#include "b.cpp"\n#include "c.h"\n'
    ),
    "a.cpp": (
        "// @A always, IMPL_A, impl\n"
        "#ifdef UNITY_FLAG\n// @A unity, IMPL_A_UNITY, impl\n"
        "#else\n// @A no unity, IMPL_A_NO_UNITY, impl\n#endif\n"
    ),
    "b.cpp": (
        "#ifdef AFTER_A\n// @B after a, IMPL_B_AFTER_A, impl\n"
        "#else\n// @B before a, IMPL_B_BEFORE_A, impl\n#endif\n"
    ),
    "c.h": (
        "#ifdef UNITY_FLAG\n// @C unity, IMPL_C_UNITY, impl\n"
        "#else\n// @C standalone, IMPL_C_STANDALONE, impl\n#endif\n"
    ),
}


def test_a_unity_layout_reads_each_source_through_its_includer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both included sources are read under the unity entry's ``-D`` and its main
    file's own context (``AFTER_A`` is defined between the two includes), a marker in
    an arm the inclusion skips is not extracted, the includer is parsed ONCE for both,
    and nothing is warned. A header keeps its standalone parse with the configured
    defines, even when the unity file includes it."""
    _write(tmp_path, UNITY)
    db = _db(tmp_path, [{"file": "unity.cpp", "args": ["-DUNITY_FLAG=1"]}])
    parsed: list[Path] = []
    real_parse = libclang_parser.parse_translation_unit

    def counting_parse(file_path: Path, args: list[str]) -> object:
        parsed.append(file_path)
        return real_parse(file_path, args)

    monkeypatch.setattr(libclang_parser, "parse_translation_unit", counting_parse)
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)

    analyse = _run(tmp_path, ["a.cpp", "b.cpp", "c.h"], db)

    assert _ids(analyse) == {
        ("a.cpp", "IMPL_A"),
        ("a.cpp", "IMPL_A_UNITY"),
        ("b.cpp", "IMPL_B_AFTER_A"),
        ("c.h", "IMPL_C_STANDALONE"),
    }
    assert parsed.count((tmp_path / "unity.cpp").resolve()) == 1
    assert recorder.warnings == []
    # the included sources keep their own path and rows
    rows = {n.need["id"]: n.source_map["start"]["row"] for n in analyse.oneline_needs}
    assert rows == {
        "IMPL_A": 0,
        "IMPL_A_UNITY": 2,
        "IMPL_B_AFTER_A": 1,
        "IMPL_C_STANDALONE": 3,
    }


def test_the_includer_is_the_first_by_path_whatever_the_database_order(
    tmp_path: Path,
) -> None:
    """Two entries include the source; the one whose main file sorts first is the
    includer, in either database order."""
    files = {
        "a_unity.cpp": '#include "s.cpp"\n',
        "b_unity.cpp": '#include "s.cpp"\n',
        "s.cpp": (
            "#if PICK == 1\n// @a, IMPL_PICK_A, impl\n"
            "#elif PICK == 2\n// @b, IMPL_PICK_B, impl\n#endif\n"
        ),
    }
    _write(tmp_path, files)
    a = {"file": "a_unity.cpp", "args": ["-DPICK=1"]}
    b = {"file": "b_unity.cpp", "args": ["-DPICK=2"]}
    for order in ([a, b], [b, a]):
        db = _db(tmp_path, order)
        assert _ids(_run(tmp_path, ["s.cpp"], db)) == {("s.cpp", "IMPL_PICK_A")}


@pytest.mark.parametrize(
    "first",
    [
        pytest.param('#if 0\n#include "s.cpp"\n#endif\n', id="if-0"),
        pytest.param('/*\n#include "s.cpp"\n*/\n', id="block-comment"),
        pytest.param('#include "missing/s.cpp"\n', id="names-another-file"),
    ],
)
def test_an_include_the_parse_does_not_confirm_is_no_includer(
    tmp_path: Path, first: str
) -> None:
    """The entry that sorts first does not include the source: its include is in an
    ``#if 0`` arm (a lexical candidate the parse refuses), in a comment (no candidate
    at all), or names another file. The next entry, which includes it, is the
    includer."""
    _write(
        tmp_path,
        {
            "a_unity.cpp": first,
            "b_unity.cpp": '#include "s.cpp"\n',
            "s.cpp": "#if PICK == 2\n// @b, IMPL_PICK_B, impl\n#endif\n",
        },
    )
    db = _db(
        tmp_path,
        [
            {"file": "a_unity.cpp", "args": ["-DPICK=1"]},
            {"file": "b_unity.cpp", "args": ["-DPICK=2"]},
        ],
    )
    assert _ids(_run(tmp_path, ["s.cpp"], db)) == {("s.cpp", "IMPL_PICK_B")}


@pytest.mark.parametrize(
    "unity",
    [
        pytest.param('#if 0\n#include "s.cpp"\n#endif\n', id="if-0"),
        pytest.param('/* #include "s.cpp" */\n', id="block-comment"),
        pytest.param("int nothing;\n", id="no-include"),
    ],
)
def test_a_source_with_no_includer_is_skipped_with_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unity: str
) -> None:
    """No entry includes the source (an ``#if 0`` include and a commented one are not
    inclusions): it is skipped as before, with one warning naming the source and the
    database, subtype ``not_in_compile_database``; it is not parsed with the
    configured defines."""
    _write(
        tmp_path,
        {"unity.cpp": unity, "s.cpp": "// @s, IMPL_S, impl\nvoid s() {}\n"},
    )
    db = _db(tmp_path, [{"file": "unity.cpp", "args": []}])
    recorder = _RecordingLogger()
    monkeypatch.setattr(analyse_module, "logger", recorder)

    analyse = _run(tmp_path, ["s.cpp"], db, defines=["ANY=1"])

    assert _ids(analyse) == set()
    source = tmp_path / "s.cpp"
    assert recorder.warnings == [
        (
            f"codelinks: skipping {source} — it has no entry in {db} and no entry "
            f"of it includes it",
            "not_in_compile_database",
        )
    ]


def test_an_includer_libclang_cannot_load_confirms_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An includer whose parse fails to load is skipped in favour of the next
    candidate, and is tried once per run."""
    _write(
        tmp_path,
        {
            "a_unity.cpp": '#include "s.cpp"\n#include "t.cpp"\n',
            "b_unity.cpp": '#include "s.cpp"\n#include "t.cpp"\n',
            "s.cpp": "// @s, IMPL_S, impl\n",
            "t.cpp": "// @t, IMPL_T, impl\n",
        },
    )
    db = _db(
        tmp_path,
        [{"file": "a_unity.cpp", "args": []}, {"file": "b_unity.cpp", "args": []}],
    )
    error = loader.load_clang_cindex().TranslationUnitLoadError
    real_parse = libclang_parser.parse_translation_unit
    tried: list[str] = []

    def failing_a(file_path: Path, args: list[str]) -> object:
        tried.append(file_path.name)
        if file_path.name == "a_unity.cpp":
            raise error("cannot load")
        return real_parse(file_path, args)

    monkeypatch.setattr(libclang_parser, "parse_translation_unit", failing_a)

    analyse = _run(tmp_path, ["s.cpp", "t.cpp"], db)

    assert _ids(analyse) == {("s.cpp", "IMPL_S"), ("t.cpp", "IMPL_T")}
    assert tried == ["a_unity.cpp", "b_unity.cpp"]


def test_a_relative_include_dir_resolves_from_any_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A database whose ``directory`` is relative (``.``, the database's own
    directory, here ``build``) and whose ``-I`` is relative: the analysis runs in an
    unrelated directory, and the header the ``-I`` names is still found, both for the
    entry's own source and for a source read through it."""
    project = tmp_path / "project"
    _write(
        project,
        {
            "include/config.h": "#define FEATURE_ON 1\n",
            "src/own.cpp": (
                '#include "config.h"\n#ifdef FEATURE_ON\n// @own, IMPL_OWN, impl\n'
                "#endif\n"
            ),
            "src/inc.cpp": "#ifdef FEATURE_ON\n// @inc, IMPL_INC, impl\n#endif\n",
            "build/unity.cpp": '#include "config.h"\n#include "src/inc.cpp"\n',
        },
    )
    db = project / "build" / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {"directory": ".", "file": f, "arguments": ["clang++", *a, "-c", f]}
                for f, a in (
                    ("../src/own.cpp", ["-I../include"]),
                    ("unity.cpp", ["-I../include", "-I.."]),
                )
            ]
        ),
        encoding="utf-8",
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    analyse = _run(project, ["src/own.cpp", "src/inc.cpp"], db)

    assert _ids(analyse) == {("own.cpp", "IMPL_OWN"), ("inc.cpp", "IMPL_INC")}


def test_first_inclusion_skipped_ranges_are_one_inclusions(tmp_path: Path) -> None:
    """libclang's per-file skipped ranges are the file's FIRST inclusion's: a file
    included twice, under two values of a macro, reports the arm the first inclusion
    skipped, while the unit's ranges hold both inclusions'."""
    _write(
        tmp_path,
        {
            "s.cpp": "#if PASS == 1\nint one;\n#else\nint two;\n#endif\n",
            "unity.cpp": (
                '#define PASS 1\n#include "s.cpp"\n#undef PASS\n'
                '#define PASS 2\n#include "s.cpp"\n'
            ),
        },
    )
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "unity.cpp", [f"-working-directory={tmp_path}"]
    )
    file = tu.get_file(str(tmp_path / "s.cpp"))

    first = loader.get_first_inclusion_skipped_ranges(tu, file)
    every = loader.get_all_skipped_ranges(tu)

    assert [(r.start_line, r.end_line) for r in first] == [(3, 5)]
    assert sorted((r.start_line, r.end_line) for r in every) == [(1, 3), (3, 5)]
    assert libclang_parser.main_file_inclusions(tu, tmp_path) == {
        (tmp_path / "s.cpp").resolve()
    }


#: a project with a unity entry in ``build/``, its relative ``directory`` and ``-I``
UNITY_PROJECT = {
    "toml_extra": (
        "\n[codelinks.projects.src.analyse.preprocessor]\n"
        'compile_commands = "../build/compile_commands.json"\n'
    ),
    "files": {
        "build/compile_commands.json": json.dumps(
            [
                {
                    "directory": ".",
                    "file": "unity.cpp",
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-I../src",
                        "-DUNITY_FLAG=1",
                        "-c",
                        "unity.cpp",
                    ],
                }
            ]
        ),
        "build/unity.cpp": '#include "refs.cpp"\n#include "a.cpp"\n',
        "src/a.cpp": (
            "#ifdef UNITY_FLAG\n// @a on, IMPL_A_ON, impl\n"
            "#else\n// @a off, IMPL_A_OFF, impl\n#endif\nvoid a() {}\n"
        ),
        "src/orphan.cpp": "// @orphan, IMPL_ORPHAN, impl\nvoid orphan() {}\n",
    },
}


def test_a_build_traces_the_sources_a_unity_entry_includes(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """A ``src-trace`` build over a unity layout whose database sits in ``build/``,
    with a relative ``directory`` and ``-I``: the needs of the sources the unity entry
    includes are created under its ``-D``, the one in an arm the inclusion skips is
    not, and the source no entry includes is skipped with one
    ``codelinks.not_in_compile_database`` warning (at analysis, so before the fixture's
    own dangling reference, which is reported at the attach)."""
    _project(tmp_path, **UNITY_PROJECT)

    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert "IMPL_A_ON" in needs
    assert "IMPL_A_OFF" not in needs
    assert "IMPL_ORPHAN" not in needs
    suffix = " [codelinks.not_in_compile_database]" if _SHOWS_WARNING_TYPES else ""
    database = tmp_path / "build" / "compile_commands.json"
    assert build_warnings(app) == [
        f"WARNING: codelinks: skipping {tmp_path / 'src' / 'orphan.cpp'} — it has no "
        f"entry in {database} and no entry of it includes it{suffix}",
        DANGLING,
    ]


def test_a_build_survives_an_include_the_parse_cannot_find(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """The unity file of :data:`UNITY_PROJECT` also includes ``<stddef.h>``, which
    libclang cannot find without its builtin headers: the build still succeeds, and
    the source the unity file includes is still read through it."""
    files = dict(UNITY_PROJECT["files"])
    files["build/unity.cpp"] = "#include <stddef.h>\n" + files["build/unity.cpp"]
    _project(tmp_path, toml_extra=UNITY_PROJECT["toml_extra"], files=files)

    app = _build(tmp_path, make_app)

    needs = _json(app)["needs"]
    assert "IMPL_A_ON" in needs
    assert "IMPL_A_OFF" not in needs


def test_an_environment_pickled_at_env_version_4_is_read_again(
    tmp_path: Path, make_app: Callable[..., SphinxTestApp]
) -> None:
    """An environment of ``env_version`` 4 holds records the libclang engine extracted
    without the entry's working directory and without includers: a source a unity
    entry includes had none. Nothing in the sources or the configuration changed:
    ``env_version`` 5 is what has the build discard it and read every document
    again, rather than keep those records."""
    _project(tmp_path, **UNITY_PROJECT)
    app = _build(tmp_path, make_app)
    pickled = Path(app.doctreedir, "environment.pickle")
    env = pickle.loads(pickled.read_bytes())
    env.version["sphinx_codelinks"] = 4
    pickled.write_bytes(pickle.dumps(env, pickle.HIGHEST_PROTOCOL))

    app = _build(tmp_path, make_app, freshenv=False)

    status = strip_colors(app._status.getvalue())
    assert (
        "loading pickled environment... failed: build environment version not current"
        in status
    )
    assert "IMPL_A_ON" in _json(app)["needs"]


def test_only_the_main_files_own_include_confirms_an_includer(tmp_path: Path) -> None:
    """The inclusions that confirm an includer are its main file's own: a source the
    unit compiles through a header of the main file is not one of them (no transitive
    includers), even when the main file's own ``#include`` of it, in an ``#if 0`` arm,
    made the entry a lexical candidate. The shared case
    ``tu_source_included_only_through_a_header_is_skipped_libclang`` pins the run."""
    _write(
        tmp_path,
        {
            "unity.cpp": '#if 0\n#include "s.cpp"\n#endif\n#include "through.h"\n',
            "through.h": '#include "s.cpp"\n',
            "s.cpp": "int s;\n",
        },
    )
    tu = libclang_parser.parse_translation_unit(
        tmp_path / "unity.cpp", [f"-working-directory={tmp_path}"]
    )

    assert libclang_parser.main_file_inclusions(tu, tmp_path) == {
        (tmp_path / "through.h").resolve()
    }


@pytest.mark.parametrize(
    "unity",
    [
        pytest.param('#include <stddef.h>\n#include "s.cpp"\n', id="system-before"),
        pytest.param('#include "missing.h"\n#include "s.cpp"\n', id="quoted-before"),
        pytest.param(
            '#include "s.cpp"\n#include "generated_config.h"\n', id="quoted-after"
        ),
        pytest.param('#include <no/such/header.h>\n#include "s.cpp"\n', id="angled"),
    ],
)
def test_an_include_the_parse_cannot_find_does_not_stop_an_includer(
    tmp_path: Path, unity: str
) -> None:
    """An ``#include`` of the main file that libclang cannot resolve -- a builtin
    header such as ``<stddef.h>``, which the wheel does not ship, or a header not yet
    generated -- has no included file: it confirms nothing and is passed over, and
    the main file's include of the source still confirms it."""
    _write(
        tmp_path,
        {
            "unity.cpp": unity,
            "s.cpp": "#ifdef UNITY_FLAG\n// @s, IMPL_S, impl\n#endif\n",
        },
    )
    db = _db(tmp_path, [{"file": "unity.cpp", "args": ["-DUNITY_FLAG=1"]}])

    assert _ids(_run(tmp_path, ["s.cpp"], db)) == {("s.cpp", "IMPL_S")}


def test_one_includer_unit_is_alive_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each includer's translation unit is released before the next is parsed, so
    memory does not grow with the number of includers: three unity entries, each
    including one source, never have two units alive. Every source is still read,
    each through its own includer, and each includer is parsed once."""
    files = {}
    for name in ("a", "b", "c"):
        files[f"u_{name}.cpp"] = f'#include "{name}.cpp"\n'
        files[f"{name}.cpp"] = (
            f"#ifdef ON_{name}\n// @{name}, IMPL_{name}, impl\n#endif\n"
        )
    _write(tmp_path, files)
    db = _db(
        tmp_path,
        [{"file": f"u_{n}.cpp", "args": [f"-DON_{n}=1"]} for n in ("c", "a", "b")],
    )
    live: list[int] = [0]
    peak: list[int] = [0]
    parsed: list[str] = []
    real_parse = libclang_parser.parse_translation_unit

    def tracking_parse(file_path: Path, args: list[str]) -> object:
        tu = real_parse(file_path, args)
        parsed.append(file_path.name)
        live[0] += 1
        peak[0] = max(peak[0], live[0])
        weakref.finalize(tu, lambda: live.__setitem__(0, live[0] - 1))
        return tu

    monkeypatch.setattr(libclang_parser, "parse_translation_unit", tracking_parse)

    analyse = _run(tmp_path, ["a.cpp", "b.cpp", "c.cpp"], db)

    assert _ids(analyse) == {
        ("a.cpp", "IMPL_a"),
        ("b.cpp", "IMPL_b"),
        ("c.cpp", "IMPL_c"),
    }
    assert sorted(parsed) == ["u_a.cpp", "u_b.cpp", "u_c.cpp"]
    assert peak[0] == 1
