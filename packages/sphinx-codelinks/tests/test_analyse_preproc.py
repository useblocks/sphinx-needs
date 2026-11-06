import json
from pathlib import Path

import pytest

pytest.importorskip("clang.cindex")

from sphinx_codelinks.analyse import analyse as analyse_module
from sphinx_codelinks.analyse.analyse import SourceAnalyse
from sphinx_codelinks.analyse.preproc import libclang_parser
from sphinx_codelinks.config import PreprocessorConfig, SourceAnalyseConfig

FIXTURE = Path(__file__).parent / "data" / "preproc" / "variants_branching.cpp"
HEADER = Path(__file__).parent / "data" / "preproc" / "header_standalone.hpp"


def _run_get_oneline_ids(defines):
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE],
        src_dir=FIXTURE.parent,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        preprocessor=PreprocessorConfig(defines=defines),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return {n.need["id"] for n in analyse.oneline_needs}


def test_libclang_engine_excludes_inactive_markers():
    ids = _run_get_oneline_ids(
        ["VARIANT_A=1", "PLATFORM_LINUX=1", "PROTOCOL_VERSION=3"]
    )
    assert "IMPL_ALWAYS" in ids
    assert "IMPL_VAR_A" in ids
    assert "IMPL_VAR_B" not in ids  # inactive
    assert "IMPL_PROTO_3" in ids
    assert "IMPL_LINUX_A" in ids


def test_libclang_engine_other_variant():
    ids = _run_get_oneline_ids(["PROTOCOL_VERSION=1"])
    assert "IMPL_ALWAYS" in ids
    assert "IMPL_VAR_B" in ids
    assert "IMPL_VAR_A" not in ids
    assert "IMPL_PROTO_3" not in ids


def test_libclang_engine_via_compile_commands(tmp_path):
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(FIXTURE.parent),
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-DVARIANT_A=1",
                        "-DPROTOCOL_VERSION=3",
                        "-c",
                        str(FIXTURE),
                    ],
                    "file": str(FIXTURE),
                }
            ]
        )
    )
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE],
        src_dir=FIXTURE.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert "IMPL_VAR_A" in ids
    assert "IMPL_VAR_B" not in ids
    assert "IMPL_PROTO_3" in ids
    assert "IMPL_LINUX_A" not in ids


def test_libclang_resilient_to_broken_code():
    broken = FIXTURE.parent / "variants_broken.cpp"
    cfg = SourceAnalyseConfig(
        src_files=[broken],
        src_dir=broken.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=[]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert ids == {"IMPL_DESPITE", "IMPL_AFTER_BROKEN"}


def test_libclang_resilient_to_half_typed_code():
    half = FIXTURE.parent / "half_typed.cpp"
    cfg = SourceAnalyseConfig(
        src_files=[half],
        src_dir=half.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=[]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    # All 4 markers survive at the token level even though 2 decls don't parse.
    assert {"IMPL_COMPLETE", "IMPL_HALF", "IMPL_AFTER", "IMPL_MID"} <= ids


def test_null_tu_warns_and_skips_but_batch_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A file whose translation unit cannot be loaded at all is skipped with a
    WARNING (not silently), and the rest of the batch still extracts.

    Real sources are recoverable under ``incomplete`` parsing, so the NULL-TU
    guard is exercised by forcing ``extract_active_comments`` to raise the
    ``TranslationUnitLoadError`` libclang would raise for an unloadable TU."""
    import clang.cindex

    good = tmp_path / "good.cpp"
    good.write_text("// @Good, IMPL_GOOD, impl, [REQ]\n")
    bad = tmp_path / "bad.cpp"
    bad.write_text("// @Bad, IMPL_BAD, impl, [REQ]\n")
    cfg = SourceAnalyseConfig(
        src_files=[bad, good],
        src_dir=tmp_path,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=[]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None

    real = libclang_parser.extract_active_comments

    def fake(src_path, args):
        if Path(src_path).name == "bad.cpp":
            raise clang.cindex.TranslationUnitLoadError("forced NULL TU")
        return real(src_path, args)

    monkeypatch.setattr(libclang_parser, "extract_active_comments", fake)

    warnings: list[str] = []

    class _Rec:
        def warning(self, *_a: object, **_k: object) -> None:
            warnings.append("w")

        def info(self, *_a: object, **_k: object) -> None:
            pass

        def debug(self, *_a: object, **_k: object) -> None:
            pass

    monkeypatch.setattr(analyse_module, "logger", _Rec())

    analyse.run()

    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert ids == {"IMPL_GOOD"}, "bad file skipped, good file survives"
    assert warnings, "a NULL translation unit must warn, not skip silently"


def test_libclang_active_matches_treesitter_when_all_active():
    """When every branch is active, libclang output == tree-sitter output."""
    # Tree-sitter path (no preprocessor block) sees ALL markers.
    ts_cfg = SourceAnalyseConfig(
        src_files=[FIXTURE], src_dir=FIXTURE.parent, get_oneline_needs=True
    )
    ts = SourceAnalyse(ts_cfg)
    ts.git_remote_url = None
    ts.git_commit_rev = None
    ts.run()
    ts_ids = {n.need["id"] for n in ts.oneline_needs}

    # libclang with both variants' guards satisfied is impossible (#else is
    # mutually exclusive), so compare the union over both variants instead.
    a = _run_get_oneline_ids(["VARIANT_A=1", "PLATFORM_LINUX=1", "PROTOCOL_VERSION=3"])
    b = _run_get_oneline_ids(["PROTOCOL_VERSION=1"])
    assert ts_ids == (a | b)


def test_libclang_skip_file_absent_from_compile_commands(tmp_path):
    """Files absent from a compile DB are skipped (spec §3.3)."""
    # DB contains only FIXTURE; half_typed.cpp is intentionally absent.
    other = FIXTURE.parent / "half_typed.cpp"
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(FIXTURE.parent),
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-DVARIANT_A=1",
                        "-DPROTOCOL_VERSION=3",
                        "-c",
                        str(FIXTURE),
                    ],
                    "file": str(FIXTURE),
                }
            ]
        )
    )
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE, other],
        src_dir=FIXTURE.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(compile_commands=db),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    # FIXTURE is in the DB — its markers must appear.
    assert "IMPL_VAR_A" in ids
    assert "IMPL_PROTO_3" in ids
    # half_typed.cpp is NOT in the DB — it must be skipped entirely.
    assert "IMPL_COMPLETE" not in ids
    assert "IMPL_HALF" not in ids
    assert "IMPL_AFTER" not in ids
    assert "IMPL_MID" not in ids


def test_header_extracted_when_absent_from_compile_commands(tmp_path):
    """A header absent from the DB is parsed standalone, not skipped."""
    db = tmp_path / "compile_commands.json"
    db.write_text(
        json.dumps(
            [
                {
                    "directory": str(FIXTURE.parent),
                    "arguments": [
                        "clang++",
                        "-std=c++17",
                        "-DVARIANT_A=1",
                        "-c",
                        str(FIXTURE),
                    ],
                    "file": str(FIXTURE),
                }
            ]
        )
    )
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE, HEADER],
        src_dir=FIXTURE.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(compile_commands=db, defines=["VARIANT_A=1"]),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    ids = {n.need["id"] for n in analyse.oneline_needs}
    # The .cpp resolves its flags from the DB entry.
    assert "IMPL_VAR_A" in ids
    # The header is absent from the DB -> parsed standalone with global defines.
    assert "IMPL_HDR_ALWAYS" in ids
    assert "IMPL_HDR_VAR_A" in ids  # global defines carry VARIANT_A=1


def _run_header_ids(defines):
    cfg = SourceAnalyseConfig(
        src_files=[HEADER],
        src_dir=HEADER.parent,
        get_oneline_needs=True,
        preprocessor=PreprocessorConfig(defines=defines),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()
    return {n.need["id"] for n in analyse.oneline_needs}


def test_header_standalone_active_define():
    ids = _run_header_ids(["VARIANT_A=1"])
    assert "IMPL_HDR_ALWAYS" in ids  # include-guard body is active
    assert "IMPL_HDR_VAR_A" in ids  # #ifdef VARIANT_A active


def test_header_standalone_inactive_define():
    ids = _run_header_ids([])
    assert "IMPL_HDR_ALWAYS" in ids  # include-guard body still active
    assert "IMPL_HDR_VAR_A" not in ids  # #ifdef VARIANT_A inactive -> dropped


# Note: extraction-output goldens for this fixture now live in the declarative
# suite (tests/data/extraction/preproc_variants.yaml, both engines). The tests
# above cover libclang-specific behavior the declarative harness does not:
# inactive-branch exclusion via defines/compile_commands, resilience to broken or
# half-typed code, compile-DB resolution, the spec §3.3 skip, and standalone
# header handling.


PLAIN_H = Path(__file__).parent / "data" / "preproc" / "plain_header.h"


def test_libclang_extracts_c_extension_header_via_cpp_language():
    """A ``.h`` header still extracts its oneline markers (not dropped/crashing).

    Headers never appear in compile_commands.json, so they are parsed standalone
    with the global defines. libclang infers C from the ``.h`` extension; without
    pinning the language, ``-std=c++17`` makes clang reject the combo and return
    a NULL translation unit (``TranslationUnitLoadError``) — which previously
    aborted ``sphinx-build -b ubtrace -W``. The standalone flags now pin ``-x``
    to the ``-std`` (see ``defines_to_args``), so the header parses as C++ and its
    markers are extracted rather than lost.
    """
    cfg = SourceAnalyseConfig(
        src_files=[FIXTURE, PLAIN_H],
        src_dir=FIXTURE.parent,
        get_need_id_refs=False,
        get_oneline_needs=True,
        get_multiline_needs=False,
        preprocessor=PreprocessorConfig(
            defines=["VARIANT_A=1", "PLATFORM_LINUX=1", "PROTOCOL_VERSION=3"]
        ),
    )
    analyse = SourceAnalyse(cfg)
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run()  # must not raise TranslationUnitLoadError
    ids = {n.need["id"] for n in analyse.oneline_needs}
    assert "IMPL_ALWAYS" in ids  # the .cpp translation unit extracts
    assert "IMPL_HDR_PLAIN" in ids  # the .h header extracts too (parsed as C++)


#: a marker after code and a non-ASCII character, and a reference on a block's second
#: row; a one-row block-comment need, a need on a block's closing row, a form feed
#: before a reference, and a marker with no id
COLUMNS_SOURCE = (
    "int x = 1; /* \u00e9 */ // @After \u00e9, IMPL_COL, impl\n"
    "  /*\n"
    "   * @need-ids:   REQ_COL\n"
    "   */\n"
    "void f() {}\n"
    "/* @Row one, IMPL_R1, impl */\n"
    "int t; /* x\n"
    "   @Row two, IMPL_R2, impl */\n"
    "int z; /* a\f @need-ids: FF1 */\n"
    "/* @need-ids: */\n"
    "void g() {}\n"
)


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"], ids=["lf", "crlf", "cr"])
def test_libclang_columns_are_the_tree_sitter_columns(tmp_path, newline):
    """Both engines report a marker's physical column, in characters, whatever the
    line endings."""
    src = tmp_path / "columns.cpp"
    src.write_bytes(COLUMNS_SOURCE.replace("\n", newline).encode("utf-8"))

    def spans(preprocessor):
        analyse = SourceAnalyse(
            SourceAnalyseConfig(
                src_files=[src],
                src_dir=tmp_path,
                get_need_id_refs=True,
                get_oneline_needs=True,
                get_multiline_needs=False,
                preprocessor=preprocessor,
            )
        )
        analyse.git_remote_url = None
        analyse.git_commit_rev = None
        analyse.run(log_summary=False)
        return [
            (
                entry.type.value,
                entry.source_map,
                getattr(entry, "need_ids", None) or entry.need["type"],
            )
            for entry in analyse.all_marked_content
        ]

    def span(row: int, start: int, end: int) -> dict:
        return {
            "start": {"row": row, "column": start},
            "end": {"row": row, "column": end},
        }

    libclang = spans(PreprocessorConfig())
    assert libclang == spans(None)
    assert libclang == [
        ("need", span(0, 23, 46), "impl"),
        ("need-id-refs", span(2, 18, 25), ["REQ_COL"]),
        ("need", span(5, 4, 27), "impl"),
        ("need", span(7, 4, 27), "impl"),
        ("need-id-refs", span(8, 24, 27), ["FF1"]),
    ]


def _analyse_written(
    root: Path, files: dict[str, str], analysed: list[str]
) -> SourceAnalyse:
    """Write ``files`` into ``root`` and run the libclang engine over ``analysed``.

    No compilation database and no defines: a header is parsed standalone, as every
    header absent from a database is, and a source with the configured defines.
    """
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")
    analyse = SourceAnalyse(
        SourceAnalyseConfig(
            src_files=[root / name for name in analysed],
            src_dir=root,
            get_need_id_refs=False,
            get_oneline_needs=True,
            get_multiline_needs=False,
            preprocessor=PreprocessorConfig(defines=[]),
        )
    )
    analyse.git_remote_url = None
    analyse.git_commit_rev = None
    analyse.run(log_summary=False)
    return analyse


def _needs(analyse: SourceAnalyse) -> set[tuple[str, str, int]]:
    """Each one-line need as (file name, id, 0-based row)."""
    return {
        (Path(n.filepath).name, str(n.need["id"]), n.source_map["start"]["row"])
        for n in analyse.oneline_needs
    }


#: A guarded header whose include includes it back. Analysed standalone, each is the
#: translation unit's main file, and its include enters it a second time: that pass finds
#: the guard defined and skips the whole guarded body, which the file's own pass compiled.
GUARDED_PAIR = {
    "a.h": (
        "#ifndef A_H\n"
        "#define A_H\n"
        '#include "b.h"\n'
        "\n"
        "// @Function in a, IMPL_A, impl\n"
        "int a_function(void);\n"
        "\n"
        "#endif\n"
    ),
    "b.h": (
        "#ifndef B_H\n"
        "#define B_H\n"
        '#include "a.h"\n'
        "\n"
        "// @Function in b, IMPL_B, impl\n"
        "int b_function(void);\n"
        "\n"
        "#endif\n"
    ),
}

#: A guarded source that includes itself: the same second pass, without a second file.
SELF_INCLUDING = {
    "self.cpp": (
        "#ifndef SELF_CPP\n"
        "#define SELF_CPP\n"
        '#include "self.cpp"\n'
        "\n"
        "// @Function in self, IMPL_SELF, impl\n"
        "int self_function();\n"
        "\n"
        "#endif\n"
    ),
}


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        pytest.param(
            GUARDED_PAIR,
            {("a.h", "IMPL_A", 4), ("b.h", "IMPL_B", 4)},
            id="guarded-pair-standalone",
        ),
        pytest.param(
            SELF_INCLUDING, {("self.cpp", "IMPL_SELF", 4)}, id="self-including"
        ),
    ],
)
def test_libclang_keeps_markers_of_a_file_its_includes_enter_again(
    tmp_path: Path, files: dict[str, str], expected: set[tuple[str, str, int]]
) -> None:
    """A file its own includes enter again keeps the markers its own pass compiled.

    The second pass skips the guarded body, function and marker included. Only the
    analysed file's own pass decides what is skipped in it, so the marker above the
    function is extracted on its own row, attached to the file and to no entity, as
    the libclang engine attaches every marker. Before the fix the second pass's
    skipped range covered the whole file and the engine extracted nothing from it.
    """
    analyse = _analyse_written(tmp_path, files, list(files))

    assert _needs(analyse) == expected
    for need in analyse.oneline_needs:
        assert need.tagged_scope is None
        assert need.scope is None


#: A genuine ``#if 0`` block in the file's own pass, in a plain file and in a file that
#: includes itself, above the guarded body the second pass skips
IF0_PLAIN = {
    "plain.cpp": (
        "#if 0\n"
        "// @Never compiled, IMPL_OFF, impl\n"
        "int never_compiled();\n"
        "#endif\n"
        "\n"
        "// @Compiled, IMPL_ON, impl\n"
        "int compiled();\n"
    ),
}
IF0_SELF_INCLUDING = {
    "self.cpp": (
        "#ifndef SELF_CPP\n"
        "#define SELF_CPP\n"
        '#include "self.cpp"\n'
        "\n"
        "#if 0\n"
        "// @Never compiled, IMPL_OFF, impl\n"
        "int never_compiled();\n"
        "#endif\n"
        "\n"
        "// @Function in self, IMPL_SELF, impl\n"
        "int self_function();\n"
        "\n"
        "#endif\n"
    ),
}


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        pytest.param(IF0_PLAIN, {("plain.cpp", "IMPL_ON", 5)}, id="plain"),
        pytest.param(
            IF0_SELF_INCLUDING, {("self.cpp", "IMPL_SELF", 9)}, id="self-including"
        ),
    ],
)
def test_libclang_drops_a_marker_its_own_pass_skips(
    tmp_path: Path, files: dict[str, str], expected: set[tuple[str, str, int]]
) -> None:
    """A marker inside a branch the file's own pass skips is still dropped.

    Keeping only the main file's own skipped ranges must not keep a marker the file's
    own pass never compiled, whether or not a later pass enters the file again.
    """
    analyse = _analyse_written(tmp_path, files, list(files))

    assert _needs(analyse) == expected


#: An unguarded header a source includes twice, with markers before, between and after
#: the two inclusions
INCLUDED_TWICE = {
    "twice.h": (
        "// @Declared in the header, IMPL_HDR, impl\nextern int from_header;\n"
    ),
    "main.cpp": (
        "// @Before the includes, IMPL_BEFORE, impl\n"
        '#include "twice.h"\n'
        "// @Between the includes, IMPL_BETWEEN, impl\n"
        '#include "twice.h"\n'
        "\n"
        "// @Main function, IMPL_MAIN, impl\n"
        "int main_function();\n"
    ),
}


def test_libclang_unguarded_header_included_twice(tmp_path: Path) -> None:
    """An unguarded header a source includes twice changes nothing in either file.

    Analysed as its translation unit's main file, the source keeps all three of its
    markers; the header's two inclusions are not the source's own text, so its marker
    is not the source's. The header, analysed on its own, gives its marker once.
    """
    analyse = _analyse_written(tmp_path, INCLUDED_TWICE, ["main.cpp", "twice.h"])

    assert _needs(analyse) == {
        ("main.cpp", "IMPL_BEFORE", 0),
        ("main.cpp", "IMPL_BETWEEN", 2),
        ("main.cpp", "IMPL_MAIN", 5),
        ("twice.h", "IMPL_HDR", 0),
    }
    assert len(analyse.oneline_needs) == 4
